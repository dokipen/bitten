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

import asynchat
import asyncore
from email.Message import Message
from email.Parser import Parser
import mimetools
import socket
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO
import sys
import traceback

from bitten.util.xmlio import Element, parse_xml

__all__ = ['Listener', 'Initiator', 'Profile']


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

        self.listen(5)

        host, port = self.socket.getsockname()
        if not ip:
            ip = socket.gethostbyname (socket.gethostname())
        try:
            self.server_name = socket.gethostbyaddr(ip)[0]
        except socket.error:
            self.server_name = ip
        print 'Listening on %s:%s' % (self.server_name, port)

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
        conn, addr = self.accept()
        print 'Connected to %s:%s' % addr
        Session(conn, addr, self.profiles, first_channelno=2)


class Session(asynchat.async_chat):
    """A BEEP session between two peers."""

    def __init__(self, conn, addr, profiles, first_channelno=1):
        asynchat.async_chat.__init__(self, conn)
        self.addr = addr
        self.set_terminator('\r\n')

        self.profiles = profiles or {}
        self.channels = {0: Channel(self, 0, ManagementProfile())}
        self.channelno = cycle_through(first_channelno, 2147483647, step=2)
        self.inbuf = []
        self.header = self.payload = None

    def handle_connect(self):
        pass

    def handle_error(self):
        t, v = sys.exc_info()[:2]
        if t is SystemExit:
            raise t, v
        else:
            asynchat.async_chat.handle_error(self)

    def collect_incoming_data(self, data):
        self.inbuf.append(data)

    def found_terminator(self):
        """Called by async_chat when a terminator is found in the input
        stream."""
        if self.header is None:
            self.header = ''.join(self.inbuf).split(' ')
            self.inbuf = []
            if self.header[0] == 'SEQ':
                # TCP mapping frame
                raise NotImplementedError                
            else:
                try:
                    size = int(self.header[int(self.header[0] != 'ANS') - 2])
                except ValueError:
                    self.header = None
                    return
                if size == 0:
                    self.payload = ''
                    self.set_terminator('END\r\n')
                else:
                    self.set_terminator(size)
        elif self.payload is None:
            self.payload = ''.join(self.inbuf)
            self.inbuf = []
            self.set_terminator('END\r\n')
        else:
            self._handle_frame(self.header, self.payload)
            self.header = self.payload = None
            self.inbuf = []
            self.set_terminator('\r\n')

    def _handle_frame(self, header, payload):
        """Handle an incoming frame.
        
        This parses the frame header and decides which channel to pass it to.
        """
        cmd = header[0]
        if cmd == 'SEQ':
            # RFC 3081 - need to digest and implement
            raise NotImplementedError
        channel = int(header[1])
        msgno = int(header[2])
        more = header[3] == '*'
        seqno = int(header[4])
        size = int(header[5])
        if cmd == 'ANS':
            ansno = int(header[6])
        else:
            ansno = None
        self.channels[channel].handle_frame(cmd, msgno, more, seqno,
                                            ansno, payload)

    def send_frame(self, cmd, channel, msgno, more, seqno, ansno=None,
                  payload=''):
        """Send the specified data frame to the peer."""
        headerbits = [cmd, channel, msgno, more and '*' or '.', seqno,
                      len(payload)]
        if cmd == 'ANS':
            assert ansno is not None
            headerbits.append(ansno)
        header = ' '.join([str(hb) for hb in headerbits])
        self.push('\r\n'.join((header, payload, 'END', '')))

    def start_channel(self, number, profile_uri):
        profile = self.profiles[profile_uri]
        channel = Channel(self, number, profile)
        self.channels[number] = channel
        return channel

    def greeting_received(self, profiles):
        """Initiator sub-classes should override this to start the channels they
        want.
        
        @param profiles: A list of URIs of the profiles the peer claims to
                         support.
        """


class Initiator(Session):

    def __init__(self, ip, port, profiles=None, handle_greeting=None):
        Session.__init__(self, None, None, profiles or {})
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connect((ip, port))
        self.greeting_handler = handle_greeting


class Channel(object):
    """A specific channel of a BEEP session."""

    def __init__(self, session, channelno, profile):
        self.session = session
        self.channelno = channelno
        self.inqueue = {}
        self.reply_handlers = {}

        self.msgno = cycle_through(0, 2147483647)
        self.msgnos = {} # message numbers currently in use
        self.ansnos = {} # answer numbers keyed by msgno, each 0-2147483647
        self.seqno = [serial(), serial()]
        self.mime_parser = Parser()

        self.profile = profile
        self.profile.session = self.session
        self.profile.channel = self
        self.profile.handle_connect()

    def handle_frame(self, cmd, msgno, more, seqno, ansno, payload):
        # Validate and update sequence number
        if seqno != self.seqno[0]:
            raise Exception, 'Out of sync with peer' # TODO: Be nice
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
    """Abstract base class for handlers of specific BEEP profiles."""

    def __init__(self):
        self.session = None
        self.channel = None

    def handle_connect(self):
        pass

    def handle_msg(self, msgno, message):
        raise NotImplementedError

    def handle_rpy(self, msgno, message):
        raise NotImplementedError

    def handle_err(self, msgno, message):
        raise NotImplementedError

    def handle_ans(self, msgno, ansno, message):
        raise NotImplementedError

    def handle_nul(self, msgno):
        raise NotImplementedError


class ManagementProfile(Profile):
    CONTENT_TYPE = 'application/beep+xml'

    def handle_connect(self):
        greeting = Element('greeting')[
            [Element('profile', uri=k) for k in self.session.profiles.keys()]
        ]
        self.channel.send_rpy(0, MIMEMessage(greeting, self.CONTENT_TYPE))

    def handle_msg(self, msgno, message):
        assert message.get_content_type() == self.CONTENT_TYPE
        root = parse_xml(message.get_payload())
        if root.name == 'start':
            print 'Start channel %s' % root.number
            for profile in root['profile']:
                if profile.uri in self.session.profiles.keys():
                    try:
                        self.session.start_channel(int(root.number),
                                                   profile.uri)
                        message = MIMEMessage(Element('profile',
                                                      uri=profile.uri),
                                              self.CONTENT_TYPE)
                        self.channel.send_rpy(msgno, message)
                        return
                    except StandardError, e:
                        print e
            message = MIMEMessage(Element('error', code=550)[
                'All request profiles are unsupported'
            ], self.CONTENT_TYPE)
            self.channel.send_err(msgno, message)
        elif root.name == 'close':
            print 'Close channel %s' % root.number
            message = MIMEMessage(Element('ok'), self.CONTENT_TYPE)
            self.channel.send_rpy(msgno, message)
            # TODO: close the channel or, if channelno is 0, terminate the
            #       session... actually, that's done implicitly when the
            #       peer disconnects after receiving the <ok/>

    def handle_rpy(self, msgno, message):
        assert message.get_content_type() == self.CONTENT_TYPE
        root = parse_xml(message.get_payload())
        if root.name == 'greeting':
            print 'Greeting...'
            profiles = [profile.uri for profile in root['profile']]
            self.session.greeting_received(profiles)
        elif root.name == 'profile':
            # This means that the channel has been established with this
            # profile... basically a channel_start_ok message
            print 'Profile %s' % root.uri
        elif root.name == 'ok':
            # A close request for a channel has been accepted, so we can
            # close it now
            print 'OK'

    def handle_err(self, msgno, message):
        assert message.get_content_type() == self.CONTENT_TYPE
        root = parse_xml(message.get_payload())
        assert root.name == 'error'
        print root.code

    def close(self, channel=0, code=200, handle_ok=None, handle_error=None):
        def handle_reply(cmd, msgno, message):
            if handle_ok is not None and cmd == 'RPY':
                handle_ok()
            if handle_error is not None and cmd == 'ERR':
                root = parse_xml(message.get_payload())
                handle_error(int(root.code), root.gettext())
        xml = Element('close', number=channel, code=code)
        return self.channel.send_msg(MIMEMessage(xml, self.CONTENT_TYPE),
                                     handle_reply)

    def start(self, profiles, handle_ok=None, handle_error=None):
        channelno = self.session.channelno.next()
        def handle_reply(cmd, msgno, message):
            if handle_ok is not None and cmd == 'RPY':
                root = parse_xml(message.get_payload())
                selected = None
                for profile in profiles:
                    if profile.URI == root.uri:
                        selected = profile
                        break
                self.session.channels[channelno] = Channel(self.session,
                                                           channelno, profile())
                handle_ok(channelno, root.uri)
            if handle_error is not None and cmd == 'ERR':
                root = parse_xml(message.get_payload())
                handle_error(int(root.code), root.gettext())
        xml = Element('start', number=channelno)[
            [Element('profile', uri=profile.URI) for profile in profiles]
        ]
        return self.channel.send_msg(MIMEMessage(xml, self.CONTENT_TYPE),
                                     handle_reply)


def cycle_through(start, stop=None, step=1):
    """Utility generator that cycles through a defined range of numbers."""
    if stop is None:
        stop = start
        start = 0
    cur = start
    while True:
        yield cur
        cur += 1
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


class MIMEMessage(Message):
    """Simplified construction of generic MIME messages for transmission as
    payload with BEEP."""

    def __init__(self, payload, content_type=None):
        Message.__init__(self)
        if content_type:
            self.set_type(content_type)
        self.set_payload(str(payload))
        del self['MIME-Version']


# Simple echo profile implementation for testing
class EchoProfile(Profile):
    URI = 'http://www.eigenmagic.com/beep/ECHO'

    def handle_msg(self, msgno, message):
        self.channel.send_rpy(msgno, message)


if __name__ == '__main__':
    listener = Listener('127.0.0.1', 8000)
    listener.profiles[EchoProfile.URI] = EchoProfile()
    try:
        asyncore.loop()
    except KeyboardInterrupt:
        pass
