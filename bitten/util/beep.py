# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
#
# Bitten is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Trac is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
# Author: Christopher Lenz <cmlenz@gmx.de>

"""Minimal implementation of the BEEP protocol (IETF RFC 3080) based on the
`asyncore` module.

Current limitations:
 * No support for the TSL and SASL profiles.
 * No support for mapping frames (SEQ frames for TCP mapping).
 * No localization support (xml:lang attribute).
"""

import asynchat
import asyncore
import bisect
import email
from email.Message import Message
import logging
import socket
import sys
import time

from bitten.util import xmlio

__all__ = ['Listener', 'Initiator', 'Profile']

BEEP_XML = 'application/beep+xml'


class ProtocolError(Exception):
    """Generic root class for BEEP exceptions."""


class TerminateSession(Exception):
    """Signal termination of a session."""


class Listener(asyncore.dispatcher):
    """BEEP peer in the listener role.
    
    This peer opens a socket for listening to incoming connections. For each
    connection, it opens a new session: an instance of `Session` that handle
    communication with the connected peer.
    """
    def __init__(self, ip, port):
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind((ip, port))
        self.sessions = []
        self.profiles = {} # Mapping from URIs to ProfileHandler sub-classes
        self.eventqueue = []
        logging.debug('Listening to connections on %s:%d', ip, port)
        self.listen(5)

    def writable(self):
        """Called by asyncore to determine whether the channel is writable."""
        return False

    def handle_read(self):
        """Called by asyncore to signal data available for reading."""
        pass

    def readable(self):
        """Called by asyncore to determine whether the channel is readable."""
        return True

    def handle_accept(self):
        """Start a new BEEP session initiated by a peer."""
        conn, (ip, port) = self.accept()
        logging.debug('Connected to %s:%d', ip, port)
        self.sessions.append(Session(self, conn, (ip, port), self.profiles,
                                     first_channelno=2))

    def run(self, timeout=15.0, granularity=5):
        """Start listening to incoming connections."""
        socket_map = asyncore.socket_map
        last_event_check = 0
        while socket_map:
            now = int(time.time())
            if (now - last_event_check) >= granularity:
                last_event_check = now
                fired = []
                i = j = 0
                while i < len(self.eventqueue):
                    when, callback = self.eventqueue[i]
                    if now >= when:
                        fired.append(callback)
                        j = i + 1
                    else:
                        break
                    i = i + 1
                if fired:
                    self.eventqueue = self.eventqueue[j:]
                    for callback in fired:
                        callback(self, now)
            asyncore.poll(timeout)

    def schedule(self, delta, callback):
        """Schedule a function to be called.
        
        @param delta: The number of seconds after which the callback should be
                      invoked
        @param callback: The function to call
        """
        bisect.insort(self.eventqueue, (int(time.time()) + delta, callback))

    def quit(self):
        if not self.sessions:
            self.close()
            return
        def terminate_next_session(session=self, when=None):
            session = self.sessions[-1]
            def handle_ok():
                if self.sessions:
                    terminate_next_session()
                else:
                    self.close()
            def handle_error(channelno, code, message):
                logging.error('Failed to close channel %d', channelno)
            logging.info('Should close session with %s', session.addr)
            session.terminate(handle_ok=handle_ok)
        self.schedule(0, terminate_next_session)
        self.run(.5)


class Session(asynchat.async_chat):
    """A BEEP session between two peers."""

    def __init__(self, listener=None, conn=None, addr=None, profiles=None,
                 first_channelno=1):
        """Create the BEEP session.
        
        @param listener: The `Listener` this session belongs to, or `None` for
                         a session by the initiating peer
        @param conn: The connection
        @param addr: The address of the remote peer, a (IP-address, port) tuple
        @param profiles: A dictionary of supported profiles; the keys are the
                         URIs of the profiles, the values are corresponding
                         sub-classes of `ProfileHandler`
        @param first_channelno: The first channel number to request; 0 for the
                                peer in the listening role, 1 for initiators
        """
        asynchat.async_chat.__init__(self, conn)
        self.listener = listener
        self.addr = addr
        self.set_terminator('\r\n')

        self.profiles = profiles or {}
        self.inbuf = []
        self.header = self.payload = None

        self.channelno = cycle_through(first_channelno, 2147483647, step=2)
        self.channels = {0: Channel(self, 0, ManagementProfileHandler)}

    def close(self):
        if self.listener:
            logging.debug('Closing connection to %s:%s', self.addr[0],
                          self.addr[1])
            self.listener.sessions.remove(self)
        else:
            logging.info('Session terminated')
        asynchat.async_chat.close(self)

    def handle_error(self):
        """Called by asyncore when an exception is raised."""
        cls, value = sys.exc_info()[:2]
        if cls is TerminateSession:
            raise cls, value
        logging.exception(value)
        self.close()

    def collect_incoming_data(self, data):
        """Called by async_chat when data is received.
        
        Buffer the data and wait until a terminator is found."""
        self.inbuf.append(data)

    def found_terminator(self):
        """Called by async_chat when a terminator is found in the input
        stream.
        
        Parse the incoming data depending on whether it terminated on the frame
        header, playload or trailer. For the header, extract the payload size
        parameter and use it as terminator or the payload. When the trailer has
        been received, delegate to `_handle_frame()`.
        """
        if self.header is None:
            # Frame header received
            self.header = ''.join(self.inbuf).split(' ')
            self.inbuf = []
            if self.header[0] == 'SEQ':
                size = 0
            else:
                # Extract payload size to use as next terminator
                try:
                    size = int(self.header[int(self.header[0] != 'ANS') - 2])
                except ValueError:
                    # TODO: Malformed frame... should we terminate the session
                    # here?
                    logging.error('Malformed frame header: [%s]',
                                  ' '.join(self.header))
                    self.header = None
                    return
            if size == 0:
                self.payload = ''
                self.set_terminator('END\r\n')
            else:
                self.set_terminator(size)
        elif self.payload is None:
            # Frame payload received
            self.payload = ''.join(self.inbuf)
            self.inbuf = []
            self.set_terminator('END\r\n')
        else:
            # Frame trailer received
            try:
                self._handle_frame(self.header, self.payload)
            finally:
                self.header = self.payload = None
                self.inbuf = []
                self.set_terminator('\r\n')

    def _handle_frame(self, header, payload):
        """Handle an incoming frame.
        
        This parses the frame header and decides which channel to pass it to.
        """
        logging.debug('Handling frame [%s]', ' '.join(header))
        msgno = None
        channel = None
        try:
            cmd = header[0].upper()
            channel = int(header[1])
            if cmd == 'SEQ':
                ackno = int(header[2])
                window = int(header[3])
                self.channels[channel].handle_seq_frame(ackno, window)
            else:
                msgno = int(header[2])
                more = header[3] == '*'
                seqno = int(header[4])
                ansno = None
                if cmd == 'ANS':
                    ansno = int(header[6])
                self.channels[channel].handle_data_frame(cmd, msgno, more,
                                                         seqno, ansno, payload)
        except (ValueError, TypeError, ProtocolError), e:
            logging.exception(e)
            if channel == 0 and msgno is not None:
                self.channels[0].profile.send_error(msgno, 550, e)

    def send_data_frame(self, cmd, channel, msgno, more, seqno, ansno=None,
                  payload=''):
        """Send the specified data frame to the peer.
        
        @param cmd: The frame keyword (one of MSG, RPY, ERR, ANS, or NUL)
        @param channel: The number of the sending channel
        @param msgno: The message number
        @param more: Whether this is the last frame belonging to the message
        @param seqno: The frame-specific sequence number
        @param ansno: For ANS frames, the answer number, otherwise `None`
        @param payload: The payload of the frame
        """
        headerbits = [cmd, channel, msgno, more and '*' or '.', seqno,
                      len(payload)]
        if cmd == 'ANS':
            assert ansno is not None
            headerbits.append(ansno)
        header = ' '.join([str(bit) for bit in headerbits])
        logging.debug('Sending frame [%s]', header)
        self.push('\r\n'.join((header, payload, 'END', '')))

    def send_seq_frame(self, channel, ackno, window):
        """Send a SEQ frame to the peer.
        
        @param channel: The number of the sending channel
        @param ackno: The acknowledgement number.
        @param window: The requested window size
        """
        headerbits = ['SEQ', channel, ackno, window]
        header = ' '.join([str(bit) for bit in headerbits])
        logging.debug('Sending frame [%s]', header)
        self.push('\r\n'.join((header, 'END', '')))

    def terminate(self, handle_ok=None, handle_error=None):
        """Terminate the session by closing all channels."""
        def close_next_channel():
            channelno = max(self.channels.keys())
            def _handle_ok():
                if channelno == 0:
                    if handle_ok is not None:
                        handle_ok()
                else:
                    close_next_channel()
            def _handle_error(code, message):
                logging.error('Peer refused to close channel %d: %s (%d)',
                              channelno, message, code)
                if handle_error is not None:
                    handle_error(channelno, code, message)
                else:
                    raise ProtocolError, '%s (%d)' % (message, code)
            self.channels[0].profile.send_close(channelno, handle_ok=_handle_ok,
                                                handle_error=_handle_error)
        close_next_channel()


class Initiator(Session):
    """Root class for BEEP peers in the initiating role."""

    def __init__(self, ip, port, profiles=None):
        """Create the BEEP session.
        
        @param ip: The IP address to connect to
        @param port: The port to connect to
        @param profiles: A dictionary of the supported profiles, where the key
                         is the URI identifying the profile, and the value is a
                         `ProfileHandler` sub-class that will be instantiated to
                         handle the communication for that profile
        """
        Session.__init__(self, profiles=profiles or {})
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        logging.debug('Connecting to %s:%s', ip, port)
        self.addr = (ip, port)
        self.connect(self.addr)

    def handle_connect(self):
        """Called by asyncore when the connection is established."""
        logging.debug('Connected to peer at %s:%s', self.addr[0], self.addr[1])

    def greeting_received(self, profiles):
        """Sub-classes should override this to start the channels they need.
        
        @param profiles: A list of URIs of the profiles the peer claims to
                         support.
        """
        pass

    def run(self):
        """Start this peer, which will try to connect to the server and send a
        greeting.
        """
        try:
            asyncore.loop()
        except TerminateSession, e:
            logging.info('Terminating session')
            self.terminate()

    def quit(self):
        self.terminate()
        asyncore.loop(timeout=10)


class Channel(object):
    """A specific channel of a BEEP session."""

    def __init__(self, session, channelno, profile_cls):
        """Create the channel.

        @param session The `Session` object that the channel belongs to
        @param channelno The channel number
        @param profile The associated `ProfileHandler` class
        """
        self.session = session
        self.channelno = channelno
        self.windowsize = 4096
        self.inqueue = {}
        self.reply_handlers = {}

        self.msgno = cycle_through(0, 2147483647)
        self.msgnos = {} # message numbers currently in use
        self.ansnos = {} # answer numbers keyed by msgno, each 0-2147483647

        # incoming, outgoing sequence numbers
        self.seqno = [SerialNumber(), SerialNumber()]

        self.profile = profile_cls(self)
        self.profile.handle_connect()

    def close(self):
        """Close the channel."""
        self.profile.handle_disconnect()
        del self.session.channels[self.channelno]

    def handle_seq_frame(self, ackno, window):
        """Process a TCP mapping frame (SEQ).
        
        @param ackno: the value of the next sequence number that the sender is
                      expecting to receive on this channel
        @param window: window size, the number of payload octets per frame that
                       the sender is expecting to receive on this channel
        """
        self.windowsize = window

    def handle_data_frame(self, cmd, msgno, more, seqno, ansno, payload):
        """Process a single data frame.

        @param cmd: The frame keyword (MSG, RPY, ERR, ANS or NUL)
        @param msgno: The message number
        @param more: `True` if more frames are pending for this message
        @param seqno: Sequence number of the frame
        @param ansno: The answer number for 'ANS' messages, otherwise `None`
        @param payload: The frame payload as a string
        """
        # Validate and update sequence number
        if seqno != self.seqno[0]:
            raise ProtocolError, 'Out of sync with peer' # TODO: Be nice
        self.seqno[0] += len(payload)

        if more:
            # More of this message pending, so push it on the queue
            self.inqueue.setdefault(msgno, []).append(payload)
            return

        # Complete message received, so handle it
        if msgno in self.inqueue:
            # Recombine queued messages
            payload = ''.join(self.inqueue[msgno]) + payload
            del self.inqueue[msgno]
        if cmd == 'RPY' and msgno in self.msgnos:
            # Final reply using this message number, so dealloc
            del self.msgnos[msgno]
        message = None
        if payload:
            message = email.message_from_string(payload)

        if cmd == 'MSG':
            self.profile.handle_msg(msgno, message)
        else:
            if msgno in self.reply_handlers:
                try:
                    self.reply_handlers[msgno](cmd, msgno, message)
                finally:
                    del self.reply_handlers[msgno]
            elif cmd == 'RPY':
                self.profile.handle_rpy(msgno, message)
            elif cmd == 'ERR':
                self.profile.handle_err(msgno, message)
            elif cmd == 'ANS':
                self.profile.handle_ans(msgno, ansno, message)
            elif cmd == 'NUL':
                self.profile.handle_nul(msgno)

    def _send(self, cmd, msgno, ansno=None, message=None):
        """Send a frame to the peer."""
        payload = ''
        if message is not None:
            payload = message.as_string()

        # If the size of the payload exceeds the current negotiated window size,
        # fragment the message and send in smaller chunks
        while len(payload) > self.windowsize:
            window = payload[:self.windowsize]
            self.session.send_data_frame(cmd, self.channelno, msgno, True,
                                         self.seqno[1].value, payload=window,
                                         ansno=ansno)
            self.seqno[1] += self.windowsize
            payload = payload[self.windowsize:]

        # Send the final frame
        self.session.send_data_frame(cmd, self.channelno, msgno, False,
                                     self.seqno[1].value, payload=payload,
                                     ansno=ansno)
        self.seqno[1] += len(payload)

    def send_msg(self, message, handle_reply=None):
        """Send a MSG frame to the peer."""
        while True: # Find a unique message number
            msgno = self.msgno.next()
            if msgno not in self.msgnos:
                break
        self.msgnos[msgno] = True # Flag the chosen message number as in use
        if handle_reply is not None:
            self.reply_handlers[msgno] = handle_reply
        self._send('MSG', msgno, None, message)
        return msgno

    def send_rpy(self, msgno, message):
        """Send a RPY frame to the peer.
        
        @param msgno: The number of the message this reply is in reference to
        @param message: The message payload (a `MIMEMessage` instance)
        """
        self._send('RPY', msgno, None, message)

    def send_err(self, msgno, message):
        """Send an ERR frame to the peer.
        
        @param msgno: The number of the message this reply is in reference to
        @param message: The message payload (a `MIMEMessage` instance)
        """
        self._send('ERR', msgno, None, message)

    def send_ans(self, msgno, message):
        """Send an ANS frame to the peer.
        
        @param msgno: The number of the message this reply is in reference to
        @param message: The message payload (a `MIMEMessage` instance)
        """
        ansnos = self.ansnos.setdefault(msgno, cycle_through(0, 2147483647))
        next_ansno = ansnos.next()
        self._send('ANS', msgno, next_ansno, message)
        return next_ansno

    def send_nul(self, msgno):
        """Send a NUL frame to the peer.
        
        @param msgno: The number of the message this reply is in reference to
        """
        self._send('NUL', msgno)
        del self.ansnos[msgno] # dealloc answer numbers for the message


class ProfileHandler(object):
    """Abstract base class for handlers of specific BEEP profiles.
    
    Concrete subclasses need to at least implement the `handle_msg()` method,
    and may override any of the others.
    """

    def __init__(self, channel):
        """Create the profile."""
        self.session = channel.session
        self.channel = channel

    def handle_connect(self):
        """Called when the channel this profile is associated with is
        initially started."""

    def handle_disconnect(self):
        """Called when the channel this profile is associated with is closed."""

    def handle_msg(self, msgno, message):
        """Handle a MSG frame."""
        raise NotImplementedError

    def handle_rpy(self, msgno, message):
        """Handle a RPY frame."""
        pass

    def handle_err(self, msgno, message):
        """Handle an ERR frame."""
        pass

    def handle_ans(self, msgno, ansno, message):
        """Handle an ANS frame."""
        pass

    def handle_nul(self, msgno):
        """Handle a NUL frame."""
        pass


class ManagementProfileHandler(ProfileHandler):
    """Implementation of the BEEP management profile."""

    def handle_connect(self):
        """Send a greeting reply directly after connecting to the peer."""
        profile_uris = self.session.profiles.keys()
        logging.debug('Send greeting with profiles: %s', profile_uris)
        xml = xmlio.Element('greeting')[
            [xmlio.Element('profile', uri=uri) for uri in profile_uris]
        ]
        self.channel.send_rpy(0, MIMEMessage(xml))

    def handle_msg(self, msgno, message):
        """Handle an incoming message."""
        assert message.get_content_type() == BEEP_XML
        elem = xmlio.parse(message.get_payload())

        if elem.tagname == 'start':
            channelno = int(elem.number)
            if channelno in self.session.channels:
                self.send_error(msgno, 550, 'Channel already in use')
                return
            for profile in elem['profile']:
                if profile.uri in self.session.profiles:
                    logging.debug('Start channel %s for profile <%s>',
                                  elem.number, profile.uri)
                    channel = Channel(self.session, channelno,
                                      self.session.profiles[profile.uri])
                    self.session.channels[channelno] = channel
                    xml = xmlio.Element('profile', uri=profile.uri)
                    self.channel.send_rpy(msgno, MIMEMessage(xml))
                    return
            self.send_error(msgno, 550,
                            'None of the requested profiles is supported')

        elif elem.tagname == 'close':
            channelno = int(elem.number)
            if not channelno in self.session.channels:
                self.send_error(msgno, 550, 'Channel not open')
                return
            if channelno == 0:
                if len(self.session.channels) > 1:
                    self.send_error(msgno, 550, 'Other channels still open')
                    return
            if self.session.channels[channelno].msgnos:
                self.send_error(msgno, 550, 'Channel waiting for replies')
                return
            self.session.channels[channelno].close()
            self.channel.send_rpy(msgno, MIMEMessage(xmlio.Element('ok')))
            if not self.session.channels:
                self.session.close()

    def handle_rpy(self, msgno, message):
        """Handle a positive reply."""
        assert message.get_content_type() == BEEP_XML
        elem = xmlio.parse(message.get_payload())

        if elem.tagname == 'greeting':
            if isinstance(self.session, Initiator):
                profiles = [profile.uri for profile in elem['profile']]
                self.session.greeting_received(profiles)

        else: # <profile/> and <ok/> are handled by callbacks
            self.send_error(msgno, 501, 'What are you replying to, son?')

    def handle_err(self, msgno, message):
        """Handle a negative reply."""
        # Probably an error on connect, because other errors should get handled
        # by the corresponding callbacks
        # TODO: Terminate the session, I guess
        assert message.get_content_type() == BEEP_XML
        elem = xmlio.parse(message.get_payload())
        assert elem.tagname == 'error'
        logging.warning('Received error in response to message #%d: %s (%d)',
                        msgno, elem.gettext(), int(elem.code))

    def send_close(self, channelno=0, code=200, handle_ok=None,
                   handle_error=None):
        """Send a request to close a channel to the peer."""
        def handle_reply(cmd, msgno, message):
            if cmd == 'RPY':
                logging.debug('Channel %d closed', channelno)
                self.session.channels[channelno].close()
                if not self.session.channels:
                    self.session.close()
                if handle_ok is not None:
                    handle_ok()
            elif cmd == 'ERR':
                elem = xmlio.parse(message.get_payload())
                text = elem.gettext()
                code = int(elem.code)
                logging.debug('Peer refused to start channel %d: %s (%d)',
                              channelno, text, code)
                if handle_error is not None:
                    handle_error(code, text)

        logging.debug('Requesting closure of channel %d', channelno)
        xml = xmlio.Element('close', number=channelno, code=code)
        return self.channel.send_msg(MIMEMessage(xml), handle_reply)

    def send_error(self, msgno, code, message=''):
        """Send an error reply to the peer."""
        logging.warning('%s (%d)', message, code)
        xml = xmlio.Element('error', code=code)[message]
        self.channel.send_err(msgno, MIMEMessage(xml))

    def send_start(self, profiles, handle_ok=None, handle_error=None):
        """Send a request to start a new channel to the peer.
        
        @param profiles A list of profiles to request for the channel, each
                        element being an instance of a `ProfileHandler`
                        sub-class
        @param handle_ok An optional callback function that will be invoked when
                         the channel has been successfully started
        @param handle_error An optional callback function that will be invoked
                            when the peer refuses to start the channel
        """
        channelno = self.session.channelno.next()
        def handle_reply(cmd, msgno, message):
            if cmd == 'RPY':
                elem = xmlio.parse(message.get_payload())
                for cls in [cls for cls in profiles if cls.URI == elem.uri]:
                    logging.debug('Channel %d started with profile %s',
                                  channelno, elem.uri)
                    self.session.channels[channelno] = Channel(self.session,
                                                               channelno, cls)
                    break
                if handle_ok is not None:
                    handle_ok(channelno, elem.uri)
            elif cmd == 'ERR':
                elem = xmlio.parse(message.get_payload())
                text = elem.gettext()
                code = int(elem.code)
                logging.debug('Peer refused to start channel %d: %s (%d)',
                              channelno, text, code)
                if handle_error is not None:
                    handle_error(code, text)

        logging.debug('Requesting start of channel %d with profiles %s',
                      channelno, [profile.URI for profile in profiles])
        xml = xmlio.Element('start', number=channelno)[
            [xmlio.Element('profile', uri=profile.URI) for profile in profiles]
        ]
        return self.channel.send_msg(MIMEMessage(xml), handle_reply)


class MIMEMessage(Message):
    """Simplified construction of generic MIME messages for transmission as
    payload with BEEP."""

    def __init__(self, payload, content_type=BEEP_XML):
        """Create the MIME message."""
        Message.__init__(self)
        if content_type:
            self.set_type(content_type)
            del self['MIME-Version']
        self.set_payload(str(payload))


def cycle_through(start, stop=None, step=1):
    """Utility generator that cycles through a defined range of numbers."""
    if stop is None:
        stop = start
        start = 0
    cur = start
    while True:
        yield cur
        cur += step
        if cur  > stop:
            cur = start


class SerialNumber(object):
    """Serial number (RFC 1982)."""

    def __init__(self, limit=4294967295L):
        self.value = 0L
        self.limit = limit

    def __ne__(self, num):
        return self.value != num

    def __eq__(self, num):
        return self.value == num

    def __iadd__(self, num):
        self.value += num
        if self.value > self.limit:
            self.value -= self.limit
        return self
