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
"""

import asynchat
import asyncore
from email.Message import Message
from email.Parser import Parser
import logging
import socket
import sys
import time

from bitten.util.xmlio import Element, parse_xml

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
        self.profiles = {}
        logging.debug('Listening to connections on %s:%d', ip, port)
        self.listen(5)

    def writable(self):
        return False

    def handle_read(self):
        pass

    def readable(self):
        return True

    def handle_connect(self):
        pass

    def handle_accept(self):
        """Start a new BEEP session."""
        conn, (ip, port) = self.accept()
        logging.debug('Connected to %s:%d', ip, port)
        Session(conn, (ip, port), self.profiles, first_channelno=2)


class Session(asynchat.async_chat):
    """A BEEP session between two peers."""

    def __init__(self, conn, addr, profiles, first_channelno=1):
        asynchat.async_chat.__init__(self, conn)
        self.addr = addr
        self.set_terminator('\r\n')

        self.profiles = profiles or {}
        self.inbuf = []
        self.header = self.payload = None
        
        self.channelno = cycle_through(first_channelno, 2147483647, step=2)
        self.channels = {0: Channel(self, 0, ManagementProfile())}

    def handle_connect(self):
        pass

    def handle_error(self):
        """Called by asyncore when an exception is raised."""
        t, v = sys.exc_info()[:2]
        if t is TerminateSession:
            raise t, v
        logging.exception(v)
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
                # TCP mapping frame
                raise NotImplementedError                
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
            msgno = int(header[2])
            more = header[3] == '*'
            seqno = int(header[4])
            size = int(header[5])
            ansno = None
            if cmd == 'ANS':
                ansno = int(header[6])
            self.channels[channel].handle_frame(cmd, msgno, more, seqno,
                                                ansno, payload)
        except (ValueError, TypeError, ProtocolError), e:
            logging.exception(e)
            if channel == 0 and msgno is not None:
                self.channels[0].profile.send_error(msgno, 550, e)

    def send_frame(self, cmd, channel, msgno, more, seqno, ansno=None,
                  payload=''):
        """Send the specified data frame to the peer."""
        headerbits = [cmd, channel, msgno, more and '*' or '.', seqno,
                      len(payload)]
        if cmd == 'ANS':
            assert ansno is not None
            headerbits.append(ansno)
        header = ' '.join([str(hb) for hb in headerbits])
        logging.debug('Sending frame [%s]', header)
        self.push('\r\n'.join((header, payload, 'END', '')))


class Initiator(Session):
    """Root class for BEEP peers in the initiating role."""

    def __init__(self, ip, port, profiles=None):
        """Create the BEEP session.
        
        @param ip: The IP address to connect to
        @param port: The port to connect to
        @param profiles: A dictionary of the supported profiles, where the key
                         is the URI identifying the profile, and the value is a
                         `Profile` instance that will handle the communication
                         for that profile
        """
        Session.__init__(self, None, None, profiles or {})
        self.terminated = False
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        logging.debug('Connecting to %s:%s', ip, port)
        try:
            self.connect((ip, port))
        except socket.error, e:
            raise TerminateSession, 'Connection to %s:%d failed' % ip, port

    def handle_close(self):
        self.terminated = True

    def greeting_received(self, profiles):
        """Sub-classes should override this to start the channels they need.
        
        @param profiles: A list of URIs of the profiles the peer claims to
                         support.
        """

    def run(self):
        """Start this peer, which will try to connect to the server and send a
        greeting.
        """
        while not self.terminated:
            try:
                asyncore.loop()
                self.terminated = True
            except (KeyboardInterrupt, TerminateSession), e:
                logging.info('Terminating session')
                self._quit()
                time.sleep(.25)

    def _quit(self):
        channelno = max(self.channels.keys())
        def handle_ok():
            if channelno == 0:
                self.terminated = True
            else:
                self._quit()
        def handle_error(code, message):
            logging.error('Peer refused to close channel %d: %s (%d)',
                          channelno, message, code)
            raise ProtocolError, '%s (%d)' % (message, code)
        self.channels[0].profile.send_close(channelno, handle_ok=handle_ok,
                                            handle_error=handle_error)


class Channel(object):
    """A specific channel of a BEEP session."""

    def __init__(self, session, channelno, profile):
        """Create the channel.

        @param session The `Session` object that the channel belongs to
        @param channelno The channel number
        @param profile The associated `Profile` object
        """
        self.session = session
        self.channelno = channelno
        self.inqueue = {}
        self.outqueue = []
        self.reply_handlers = {}

        self.msgno = cycle_through(0, 2147483647)
        self.msgnos = {} # message numbers currently in use
        self.ansnos = {} # answer numbers keyed by msgno, each 0-2147483647
        self.seqno = [serial(), serial()] # incoming, outgoing sequence numbers
        self.mime_parser = Parser()

        self.profile = profile
        self.profile.session = self.session
        self.profile.channel = self
        self.profile.handle_connect()

    def handle_frame(self, cmd, msgno, more, seqno, ansno, payload):
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
        if msgno in self.inqueue.keys():
            # Recombine queued messages
            payload = ''.join(self.inqueue[msgno]) + payload
            del self.inqueue[msgno]
        if cmd == 'RPY' and msgno in self.msgnos.keys():
            # Final reply using this message number, so dealloc
            del self.msgnos[msgno]
        message = None
        if payload:
            message = self.mime_parser.parsestr(payload)

        if cmd == 'MSG':
            self.profile.handle_msg(msgno, message)
        else:
            if msgno in self.reply_handlers.keys():
                self.reply_handlers[msgno](cmd, msgno, message)
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
        # TODO: Fragment and queue the message if necessary;
        #       First need TCP mapping (RFC 3081) for that to make real sense
        payload = ''
        if message is not None:
            payload = message.as_string()
        self.session.send_frame(cmd, self.channelno, msgno, False,
                                self.seqno[1].value, payload=payload,
                                ansno=ansno)
        self.seqno[1] += len(payload)

    def send_msg(self, message, handle_reply=None):
        while True: # Find a unique message number
            msgno = self.msgno.next()
            if msgno not in self.msgnos.keys():
                break
        self.msgnos[msgno] = True # Flag the chosen message number as in use
        if handle_reply is not None:
            self.reply_handlers[msgno] = handle_reply
        self._send('MSG', msgno, None, message)
        return msgno

    def send_rpy(self, msgno, message):
        self._send('RPY', msgno, None, message)

    def send_err(self, msgno, message):
        self._send('ERR', msgno, None, message)

    def send_ans(self, msgno, message):
        if not msgno in self.ansnos.keys():
            ansno = cycle_through(0, 2147483647)
            self.ansnos[msgno] = ansno
        else:
            ansno = self.ansnos[msgno]
        next_ansno = ansno.next()
        self._send('ANS', msgno, next_ansno, message)
        return next_ansno

    def send_nul(self, msgno):
        self._send('NUL', msgno)
        del self.ansnos[msgno] # dealloc answer numbers for the message


class Profile(object):
    """Abstract base class for handlers of specific BEEP profiles.
    
    Concrete subclasses need to at least implement the `handle_msg()` method,
    and may override any of the others.
    """

    def __init__(self):
        """Create the profile."""
        self.session = None
        self.channel = None

    def handle_connect(self):
        """Called when the channel this profile is associated with is
        initially started."""
        pass

    def handle_msg(self, msgno, message):
        raise NotImplementedError

    def handle_rpy(self, msgno, message):
        pass

    def handle_err(self, msgno, message):
        pass

    def handle_ans(self, msgno, ansno, message):
        pass

    def handle_nul(self, msgno):
        pass


class ManagementProfile(Profile):
    """Implementation of the BEEP management profile."""

    def handle_connect(self):
        """Send a greeting reply directly after connecting to the peer."""
        profile_uris = self.session.profiles.keys()
        logging.debug('Send greeting with profiles %s', profile_uris)
        greeting = Element('greeting')[
            [Element('profile', uri=k) for k in profile_uris]
        ]
        self.channel.send_rpy(0, MIMEMessage(greeting, BEEP_XML))

    def handle_msg(self, msgno, message):
        assert message.get_content_type() == BEEP_XML
        elem = parse_xml(message.get_payload())

        if elem.tagname == 'start':
            for profile in elem['profile']:
                if profile.uri in self.session.profiles.keys():
                    logging.debug('Start channel %s for profile <%s>',
                                  elem.number, profile.uri)
                    channel = Channel(self.session, int(elem.number),
                                      self.session.profiles[profile.uri])
                    self.session.channels[int(elem.number)] = channel
                    message = MIMEMessage(Element('profile', uri=profile.uri),
                                          BEEP_XML)
                    self.channel.send_rpy(msgno, message)
                    return
            self.send_error(msgno, 550,
                            'All requested profiles are unsupported')

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
            del self.session.channels[channelno]
            message = MIMEMessage(Element('ok'), BEEP_XML)
            self.channel.send_rpy(msgno, message)
            if not self.session.channels:
                self.session.close()

    def handle_rpy(self, msgno, message):
        assert message.get_content_type() == BEEP_XML
        elem = parse_xml(message.get_payload())

        if elem.tagname == 'greeting':
            if isinstance(self.session, Initiator):
                profiles = [profile.uri for profile in elem['profile']]
                self.session.greeting_received(profiles)

        else: # <profile/> and <ok/> are handled by callbacks
            self.send_error(msgno, 501, 'What are you replying to, son?')

    def handle_err(self, msgno, message):
        # Probably an error on connect, because other errors should get handled
        # by the corresponding callbacks
        # TODO: Terminate the session, I guess
        assert message.get_content_type() == BEEP_XML
        elem = parse_xml(message.get_payload())
        assert elem.tagname == 'error'
        logging.warning('Received error in response to message #%d: %s (%s)',
                        msgno, elem.gettext(), elem.code)

    def send_close(self, channelno=0, code=200, handle_ok=None,
                   handle_error=None):
        def handle_reply(cmd, msgno, message):
            if cmd == 'RPY':
                logging.debug('Channel %d closed', channelno)
                del self.session.channels[channelno]
                if handle_ok is not None:
                    handle_ok()
                if not self.session.channels:
                    logging.debug('Session terminated')
                    self.session.close()
            elif cmd == 'ERR':
                elem = parse_xml(message.get_payload())
                text = elem.gettext()
                code = int(elem.code)
                logging.debug('Peer refused to start channel %d: %s (%d)',
                              channelno, text, code)
                if handle_error is not None:
                    handle_error(code, text)

        logging.debug('Requesting closure of channel %d', channelno)
        xml = Element('close', number=channelno, code=code)
        return self.channel.send_msg(MIMEMessage(xml, BEEP_XML), handle_reply)

    def send_error(self, msgno, code, message=''):
        logging.warning('%s (%d)', message, code)
        xml = Element('error', code=code)[message]
        self.channel.send_err(msgno, MIMEMessage(xml, BEEP_XML))

    def send_start(self, profiles, handle_ok=None, handle_error=None):
        channelno = self.session.channelno.next()
        def handle_reply(cmd, msgno, message):
            if cmd == 'RPY':
                elem = parse_xml(message.get_payload())
                for profile in [p for p in profiles if p.URI == elem.uri]:
                    logging.debug('Channel %d started with profile %s',
                                  channelno, elem.uri)
                    self.session.channels[channelno] = Channel(self.session,
                                                               channelno,
                                                               profile())
                    break
                if handle_ok is not None:
                    handle_ok(channelno, elem.uri)
            elif cmd == 'ERR':
                elem = parse_xml(message.get_payload())
                text = elem.gettext()
                code = int(elem.code)
                logging.debug('Peer refused to start channel %d: %s (%d)',
                              channelno, text, code)
                if handle_error is not None:
                    handle_error(code, text)

        logging.debug('Requesting start of channel %d with profiles %s',
                      channelno, [profile.URI for profile in profiles])
        xml = Element('start', number=channelno)[
            [Element('profile', uri=profile.URI) for profile in profiles]
        ]
        return self.channel.send_msg(MIMEMessage(xml, BEEP_XML), handle_reply)


class MIMEMessage(Message):
    """Simplified construction of generic MIME messages for transmission as
    payload with BEEP."""

    def __init__(self, payload, content_type=None):
        Message.__init__(self)
        if content_type:
            self.set_type(content_type)
        self.set_payload(str(payload))
        del self['MIME-Version']


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


class serial(object):
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
