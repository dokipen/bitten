# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.cmlenz.net/wiki/License.

"""Minimal implementation of the BEEP protocol (IETF RFC 3080) based on the
`asyncore` module.

Current limitations:
 - No support for the TLS and SASL profiles.
 - No support for mapping frames (SEQ frames for TCP mapping).
 - No localization support (xml:lang attribute).
"""

import asynchat
import asyncore
from datetime import datetime, timedelta
import email
from heapq import heappop, heappush
import logging
import socket
try:
    set
except NameError:
    from sets import Set as set
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO
import sys

from bitten.util import xmlio

__all__ = ['Listener', 'Initiator', 'Payload', 'ProfileHandler',
           'ProtocolError']

BEEP_XML = 'application/beep+xml'

log = logging.getLogger('bitten.beep')


class ProtocolError(Exception):
    """Generic root class for BEEP errors."""

    _default_messages = {
        421: 'Service Not Available',
        450: 'Requested Action Not Taken',
        451: 'Requested Action Aborted',
        454: 'Temporary Authentication Failure',
        500: 'General Syntax Error',
        501: 'Syntax Error In Parameters',
        504: 'Parameter Not Implemented',
        530: 'Authentication Required',
        534: 'Authentication Mechanism Insufficient',
        535: 'Authentication Failure',
        537: 'Action Not Authorised For User',
        538: 'Authentication Mechanism Requires Encryption',
        550: 'Requested Action Not Taken',
        553: 'Parameter Invalid',
        554: 'Transaction Failed'
    }

    def __init__(self, code, message=None):
        """Create the error.
        
        A numeric error code must be provided as the first parameter. A message
        can be provided; if it is omitted, a standard error message will be
        used in case the error code is known.
        
        @param code: The error code
        @param message: An error message (optional)
        """
        if message is None:
            message = ProtocolError._default_messages.get(code)
        Exception.__init__(self, 'BEEP error %d (%s)' % (code, message))
        self.code = code
        self.message = message
        self.local = True

    def from_xml(cls, xml):
        """Create an error object from the given XML element.
        
        @param xml: The XML element representing the error
        @type xml: An instance of L{bitten.util.xmlio.ParsedElement}
        @return: The created C{ProtocolError} object
        """
        elem = xmlio.parse(xml)
        obj = cls(int(elem.attr['code']), elem.gettext())
        obj.local = False
        return obj
    from_xml = classmethod(from_xml)

    def to_xml(self):
        """Create an XML representation of the error.
        
        @return: The created XML element
        """
        return xmlio.Element('error', code=self.code)[self.message]


class TerminateSession(Exception):
    """Signal termination of a session."""


class EventLoop(object):
    """An `asyncore` event loop.
    
    This will interrupt the normal asyncore loop at configurable intervals, and
    execute scheduled callbacks.
    """

    def __init__(self):
        """Create the event loop."""
        self.eventqueue = []

    def run(self, timeout=15.0, granularity=5):
        """Start the event loop."""
        granularity = timedelta(seconds=granularity)
        socket_map = asyncore.socket_map
        last_event_check = datetime.min
        try:
            while socket_map:
                now = datetime.now()
                if now - last_event_check >= granularity:
                    last_event_check = now
                    while self.eventqueue:
                        when, callback = heappop(self.eventqueue)
                        if now < when:
                            heappush(self.eventqueue, (when, callback))
                            log.debug('Checking done %d events.',
                                      len(self.eventqueue))
                            break
                        try:
                            callback()
                        except:
                            log.error('Exception caught firing callback %s. '
                                      'Ignoring.', callback.__name__)
                try: 
                    asyncore.loop(timeout, True, None, 1)
                except: 
                    log.error('Exception caught in asyncore.loop, ignoring.');
        except:
            log.error('Exception caught in run()');


    def schedule(self, delta, callback):
        """Schedule a function to be called.
        
        @param delta: The number of seconds after which the callback should be
                      invoked
        @param callback: The function to call
        """
        when = datetime.now() + timedelta(seconds=delta)
        log.debug('Scheduling event %s to run at %s', callback.__name__, when)

        heappush(self.eventqueue, (when, callback))


class Listener(EventLoop, asyncore.dispatcher):
    """BEEP peer in the listener role.
    
    This peer opens a socket for listening to incoming connections. For each
    connection, it opens a new session: an instance of `Session` that handle
    communication with the connected peer.
    """
    def __init__(self, ip, port):
        """Create the listener.
        
        @param ip: The IP address or host name to bind to
        @type ip: a string
        @param port: The TCP port number to bind to
        @type port: an int
        """
        EventLoop.__init__(self)
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        self.bind((ip, port))
        self.sessions = []
        self.profiles = {} # Mapping from URIs to ProfileHandler sub-classes
        log.debug('Listening to connections on %s:%d', ip, port)
        self.listen(5)

    def writable(self):
        """Called by asyncore to determine whether the channel is writable."""
        return False

    def handle_read(self):
        """Called by asyncore to signal data available for reading."""

    def readable(self):
        """Called by asyncore to determine whether the channel is readable."""
        return True

    def handle_accept(self):
        """Start a new BEEP session initiated by a peer."""
        conn, (ip, port) = self.accept()
        log.debug('Connected to %s:%d', ip, port)
        self.sessions.append(Session(self, conn, (ip, port), self.profiles,
                                     first_channelno=2))

    def quit(self):
        """Shutdown the listener, attempting to gracefully quit all active BEEP
        sessions by first closing their respective channels."""
        if not self.sessions:
            self.close()
            return
        def terminate_next_session():
            session = self.sessions[-1]
            def handle_ok():
                if self.sessions:
                    terminate_next_session()
                else:
                    self.close()
            def handle_error(channelno, code, message):
                log.error('Failed to close channel %d', channelno)
            log.debug('Closing session with %s', session.addr)
            session.terminate(handle_ok=handle_ok, handle_error=handle_error)
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
        if conn:
            self.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

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
            log.debug('Closing connection to %s:%s', self.addr[0], self.addr[1])
            self.listener.sessions.remove(self)
        else:
            log.info('Session terminated')
        asynchat.async_chat.close(self)

    def handle_close(self):
        log.warning('Peer %s:%s closed connection' % self.addr)
        channels = self.channels.keys()
        channels.reverse()
        for channelno in channels:
            self.channels[channelno].close()
        asynchat.async_chat.handle_close(self)

    def handle_error(self):
        """Called by asyncore when an exception is raised."""
        cls, value = sys.exc_info()[:2]
        if cls is TerminateSession:
            raise
        log.exception(value)

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
                    log.error('Malformed frame header: [%s]',
                              ' '.join(self.header), exc_info=True)
                    self.header = None
                    raise TerminateSession('Malformed frame header')
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
        log.debug('Handling frame [%s]', ' '.join(header))
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
                assert cmd in ('MSG', 'RPY', 'ERR', 'ANS', 'NUL')
                msgno = int(header[2])
                assert header[3] in ('*', '.')
                more = header[3] == '*'
                seqno = int(header[4])
                ansno = None
                if cmd == 'ANS':
                    ansno = int(header[6])
                try:
                    self.channels[channel].handle_data_frame(cmd, msgno, more,
                                                             seqno, ansno,
                                                             payload)
                except ProtocolError, e:
                    log.error(e)
                    if e.local and msgno is not None:
                        self.channels[channel].send_err(msgno,
                                                        Payload(e.to_xml()))

        except (AssertionError, IndexError, TypeError, ValueError), e:
            log.error('Malformed frame', exc_info=True)
            raise TerminateSession('Malformed frame header')

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
                log.error('Peer refused to close channel %d: %s (%d)',
                          channelno, message, code)
                if handle_error is not None:
                    handle_error(channelno, code, message)
                else:
                    raise ProtocolError(code, message)
            self.channels[0].profile.send_close(channelno, handle_ok=_handle_ok,
                                                handle_error=_handle_error)
        close_next_channel()


class Initiator(EventLoop, Session):
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
        EventLoop.__init__(self)
        Session.__init__(self, profiles=profiles or {})
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        log.debug('Connecting to %s:%s', ip, port)
        if ip and port:
            self.addr = (ip, port)
            self.connect(self.addr)

    def handle_connect(self):
        """Called by asyncore when the connection is established."""
        log.debug('Connected to peer at %s:%s', self.addr[0], self.addr[1])

    def greeting_received(self, profiles):
        """Sub-classes should override this to start the channels they need.
        
        @param profiles: A list of URIs of the profiles the peer claims to
                         support.
        """

    def quit(self):
        """Stops the build slave, attempting to gracefully quit the session by
        closing all active channels."""
        self.terminate()
        asyncore.loop(timeout=10)


class Channel(object):
    """A specific channel of a BEEP session."""

    def __init__(self, session, channelno, profile_cls):
        """Create the channel.

        @param session: The L{Session} object that the channel belongs to
        @param channelno: The channel number
        @param profile_cls: The associated L{ProfileHandler} class
        """
        self.session = session
        self.channelno = channelno
        self.windowsize = 4096
        self.inqueue = {}
        self.reply_handlers = {}

        self.msgno = cycle_through(0, 2147483647)
        self.msgnos = set() # message numbers currently in use
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
            raise TerminateSession('Out of sync with peer')
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
        if cmd in ('ERR', 'RPY', 'NUL') and msgno in self.msgnos:
            # Final reply using this message number, so dealloc
            self.msgnos.remove(msgno)
        if payload:
            payload = Payload.parse(payload)
        else:
            payload = None

        if cmd == 'MSG':
            self.profile.handle_msg(msgno, payload)
        else:
            if msgno in self.reply_handlers:
                try:
                    self.reply_handlers[msgno](cmd, msgno, ansno, payload)
                finally:
                    if cmd != 'ANS':
                        del self.reply_handlers[msgno]
            elif cmd == 'RPY':
                self.profile.handle_rpy(msgno, payload)
            elif cmd == 'ERR':
                self.profile.handle_err(msgno, payload)
            elif cmd == 'ANS':
                self.profile.handle_ans(msgno, ansno, payload)
            elif cmd == 'NUL':
                self.profile.handle_nul(msgno)

    def send_msg(self, payload, handle_reply=None, force_flush=True):
        """Send a MSG frame to the peer.
        
        @param payload: The message payload (a `Payload` instance)
        @param handle_reply: A function that is called when a reply to this
                             message is received
        @param force_flush: Flush the beep channel after sending the message
        @return: the message number assigned to the message
        """
        while True: # Find a unique message number
            msgno = self.msgno.next()
            if msgno not in self.msgnos:
                break
        self.msgnos.add(msgno) # Flag the chosen message number as in use
        if handle_reply is not None:
            assert callable(handle_reply), 'Reply handler must be callable'
            self.reply_handlers[msgno] = handle_reply
        if force_flush == True:
            self.send_with_producer(FrameProducer(self, 'MSG', msgno, None,
                                                      payload))
        else: 
            self.session.push_with_producer(FrameProducer(self, 'MSG', msgno, None, payload))

        return msgno

    def send_rpy(self, msgno, payload):
        """Send a RPY frame to the peer.
        
        @param msgno: The number of the message this reply is in reference to
        @param payload: The message payload (a `Payload` instance)
        """
        self.send_with_producer(FrameProducer(self, 'RPY', msgno, None,
                                                      payload))

    def send_err(self, msgno, payload):
        """Send an ERR frame to the peer.
        
        @param msgno: The number of the message this reply is in reference to
        @param payload: The message payload (a `Payload` instance)
        """
        self.send_with_producer(FrameProducer(self, 'ERR', msgno, None,
                                                      payload))

    def send_ans(self, msgno, payload):
        """Send an ANS frame to the peer.
        
        @param msgno: The number of the message this reply is in reference to
        @param payload: The message payload (a `Payload` instance)
        @return: the answer number assigned to the answer
        """
        ansnos = self.ansnos.setdefault(msgno, cycle_through(0, 2147483647))
        next_ansno = ansnos.next()
        self.send_with_producer(FrameProducer(self, 'ANS', msgno,
                                                      next_ansno, payload))
        return next_ansno

    def send_nul(self, msgno):
        """Send a NUL frame to the peer.
        
        @param msgno: The number of the message this reply is in reference to
        """
        self.send_with_producer(FrameProducer(self, 'NUL', msgno))
        del self.ansnos[msgno] # dealloc answer numbers for the message

    def send_with_producer(self, fp): 
        """Sends a message contained in the given FrameProducer to the peer, 
        ensuring the message is flushed before continuing.      
        """ 
        # push with producer seems to send the first frame out the door 
        self.session.push_with_producer(fp) 
        # if there are any more, make sure they get out as well. 
        if not fp.done:  
            while not fp.done: 
               asyncore.loop(count=1) 
            # make sure to flush the last bit. 
            asyncore.loop(count=1) 

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

    def handle_msg(self, msgno, payload):
        """Handle a MSG frame.
        
        @param msgno: The message identifier
        @param payload: The C{Payload} of the message
        """
        raise NotImplementedError

    def handle_rpy(self, msgno, payload):
        """Handle a RPY frame.
        
        @param msgno: The identifier of the referenced message
        @param payload: The C{Payload} of the message
        """
        pass

    def handle_err(self, msgno, payload):
        """Handle an ERR frame.
        
        @param msgno: The identifier of the referenced message
        @param payload: The C{Payload} of the message
        """
        pass

    def handle_ans(self, msgno, ansno, payload):
        """Handle an ANS frame.
        
        @param msgno: The identifier of the referenced message
        @param ansno: The answer number
        @param payload: The C{Payload} of the message
        """
        pass

    def handle_nul(self, msgno):
        """Handle a NUL frame.
        
        @param msgno: The identifier of the referenced message
        """
        pass


class ManagementProfileHandler(ProfileHandler):
    """Implementation of the BEEP management profile."""

    def handle_connect(self):
        """Send a greeting reply directly after connecting to the peer."""
        profile_uris = self.session.profiles.keys()
        log.debug('Send greeting with profiles: %s', profile_uris)
        xml = xmlio.Element('greeting')[
            [xmlio.Element('profile', uri=uri) for uri in profile_uris]
        ]
        self.channel.send_rpy(0, Payload(xml))

    def handle_msg(self, msgno, payload):
        """Handle an incoming message."""
        assert payload and payload.content_type == BEEP_XML
        elem = xmlio.parse(payload.body)

        if elem.name == 'start':
            channelno = int(elem.attr['number'])
            if channelno in self.session.channels:
                raise ProtocolError(550, 'Channel already in use')
            for profile in elem.children('profile'):
                if profile.attr['uri'] in self.session.profiles:
                    log.debug('Start channel %s for profile <%s>',
                              elem.attr['number'], profile.attr['uri'])
                    channel = Channel(self.session, channelno,
                                      self.session.profiles[profile.attr['uri']])
                    self.session.channels[channelno] = channel
                    xml = xmlio.Element('profile', uri=profile.attr['uri'])
                    self.channel.send_rpy(msgno, Payload(xml))
                    return
            raise ProtocolError(550,
                                'None of the requested profiles is supported')

        elif elem.name == 'close':
            channelno = int(elem.attr['number'])
            if not channelno in self.session.channels:
                raise ProtocolError(550, 'Channel not open')
            if channelno == 0:
                if len(self.session.channels) > 1:
                    raise ProtocolError(550, 'Other channels still open')
            if self.session.channels[channelno].msgnos:
                raise ProtocolError(550, 'Channel waiting for replies')
            self.session.channels[channelno].close()
            self.channel.send_rpy(msgno, Payload(xmlio.Element('ok')))
            if not self.session.channels:
                self.session.close()

    def handle_rpy(self, msgno, payload):
        """Handle a positive reply."""
        if payload.content_type == BEEP_XML:
            elem = xmlio.parse(payload.body)
            if elem.name == 'greeting':
                if isinstance(self.session, Initiator):
                    profiles = [p.attr['uri'] for p in elem.children('profile')]
                    self.session.greeting_received(profiles)

    def handle_err(self, msgno, payload):
        """Handle a negative reply."""
        # Probably an error on connect, because other errors should get handled
        # by the corresponding callbacks
        # TODO: Terminate the session, I guess
        if payload.content_type == BEEP_XML:
            raise ProtocolError.from_xml(payload.body)

    def send_close(self, channelno=0, code=200, handle_ok=None,
                   handle_error=None):
        """Send a request to close a channel to the peer."""
        def handle_reply(cmd, msgno, ansno, payload):
            if cmd == 'RPY':
                log.debug('Channel %d closed', channelno)
                self.session.channels[channelno].close()
                if not self.session.channels:
                    self.session.close()
                if handle_ok is not None:
                    handle_ok()
            elif cmd == 'ERR':
                error = ProtocolError.from_xml(payload.body)
                log.debug('Peer refused to start channel %d: %s (%d)',
                          channelno, error.message, error.code)
                if handle_error is not None:
                    handle_error(error.code, error.message)

        log.debug('Requesting closure of channel %d', channelno)
        xml = xmlio.Element('close', number=channelno, code=code)
        return self.channel.send_msg(Payload(xml), handle_reply, True)

    def send_start(self, profiles, handle_ok=None, handle_error=None):
        """Send a request to start a new channel to the peer.
        
        @param profiles: A list of profiles to request for the channel, each
            element being an instance of a L{ProfileHandler} subclass
        @param handle_ok: An optional callback function that will be invoked
            when the channel has been successfully started
        @param handle_error: An optional callback function that will be invoked
            when the peer refuses to start the channel
        """
        channelno = self.session.channelno.next()
        def handle_reply(cmd, msgno, ansno, payload):
            if cmd == 'RPY':
                elem = xmlio.parse(payload.body)
                for cls in [p for p in profiles if p.URI == elem.attr['uri']]:
                    log.debug('Channel %d started with profile %s', channelno,
                              elem.attr['uri'])
                    self.session.channels[channelno] = Channel(self.session,
                                                               channelno, cls)
                    break
                if handle_ok is not None:
                    handle_ok(channelno, elem.attr['uri'])
            elif cmd == 'ERR':
                elem = xmlio.parse(payload.body)
                text = elem.gettext()
                code = int(elem.attr['code'])
                log.debug('Peer refused to start channel %d: %s (%d)',
                          channelno, text, code)
                if handle_error is not None:
                    handle_error(code, text)

        log.debug('Requesting start of channel %d with profiles %s', channelno,
                  [profile.URI for profile in profiles])
        xml = xmlio.Element('start', number=channelno)[
            [xmlio.Element('profile', uri=profile.URI) for profile in profiles]
        ]
        return self.channel.send_msg(Payload(xml), handle_reply, True)


class Payload(object):
    """MIME message for transmission as payload with BEEP."""

    def __init__(self, data=None, content_type=BEEP_XML,
                 content_disposition=None, content_encoding=None):
        """Initialize the payload object.
        
        @param data: The body of the MIME message. This can be either:
            - a string,
            - a file-like object providing a C{read()} function,
            - an XML element, or
            - C{None}
        @param content_type: the MIME type of the payload
        @param content_disposition: the filename for disposition of the data
        @param content_encoding: the encoding of the data
        """
        self._hdr_buf = None
        self.content_type = content_type
        self.content_disposition = content_disposition
        self.content_encoding = content_encoding

        if data is None:
            data = ''
        if isinstance(data, (xmlio.Element, xmlio.ParsedElement)):
            self.body = StringIO(str(data))
        elif isinstance(data, basestring):
            self.body = StringIO(data)
        else:
            assert hasattr(data, 'read'), \
                   'Payload data %s must provide a `read` method' % data
            self.body = data

    def read(self, size=None):
        """Return the specified range of the MIME message.
        
        @param size: the number of bytes to read
        """
        if self._hdr_buf is None:
            hdrs = []
            if self.content_type:
                hdrs.append('Content-Type: ' + self.content_type)
            if self.content_disposition:
                hdrs.append('Content-Disposition: ' + self.content_disposition)
            if self.content_encoding:
                hdrs.append('Content-Transfer-Encoding: ' +
                            self.content_encoding)
            hdrs.append('')
            self._hdr_buf = '\r\n'.join(hdrs) + '\r\n'
            if isinstance(self._hdr_buf, unicode):
                self._hdr_buf = self._hdr_buf.encode('utf8')

        ret_buf = ''
        if len(self._hdr_buf):
            if size is not None and len(self._hdr_buf) > size:
                ret_buf = self._hdr_buf[:size]
                self._hdr_buf = self._hdr_buf[size:]
                return ret_buf
            ret_buf = self._hdr_buf
            self._hdr_buf = ''

        if not self.body.closed:
            ret_buf = ret_buf + self.body.read((size or -1) - len(ret_buf))
            if size is None or len(ret_buf) < size:
                self.body.close()

        return ret_buf

    def parse(cls, string):
        """Create a C{Payload} object from the given string data.
        
        @param string: The string containing the MIME message.
        """
        message = email.message_from_string(string)
        content_type = message.get('Content-Type')
        content_disposition = message.get('Content-Disposition')
        content_encoding = message.get('Content-Transfer-Encoding')
        return Payload(message.get_payload(), content_type,
                       content_disposition, content_encoding)
    parse = classmethod(parse)


class FrameProducer(object):
    """Internal class that emits the frames of a BEEP message, based on the
    C{asynchat} C{push_with_producer()} protocol.
    """
    def __init__(self, channel, cmd, msgno, ansno=None, payload=None):
        """Initialize the frame producer.
        
        @param channel: The channel the message is to be sent on
        @param cmd: The BEEP command/keyword (MSG, RPY, ERR, ANS or NUL)
        @param msgno: The message number
        @param ansno: The answer number (only for ANS messages)
        @param payload: The message payload
        @type payload: an instance of L{Payload}
        """
        self.session = channel.session
        self.channel = channel
        self.cmd = cmd
        self.msgno = msgno
        self.ansno = ansno

        self.payload = payload
        self.done = False

    def more(self):
        """Called by `async_chat` when the producer has been pushed on the
        producer FIFO and the channel is about to write."""
        if self.done:
            return ''

        if self.payload:
            data = self.payload.read(self.channel.windowsize)
            if len(data) < self.channel.windowsize:
                self.done = True
        else:
            data = ''
            self.done = True

        headerbits = [self.cmd, self.channel.channelno, self.msgno,
                      self.done and '.' or '*', self.channel.seqno[1].value,
                      len(data)]
        if self.cmd == 'ANS':
            assert self.ansno is not None
            headerbits.append(self.ansno)
        header = ' '.join([str(bit) for bit in headerbits])
        log.debug('Sending frame [%s]', header)
        frame = '\r\n'.join((header, data + 'END', ''))
        self.channel.seqno[1] += len(data)

        return frame


def cycle_through(start, stop=None, step=1):
    """Utility generator that cycles through a defined range of numbers."""
    if stop is None:
        stop = start
        start = 0
    cur = start
    while True:
        yield cur
        cur += step
        if cur > stop:
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
