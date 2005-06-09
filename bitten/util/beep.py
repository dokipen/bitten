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
import traceback

from bitten.util.xmlio import Element, parse_xml

__all__ = ['Listener', 'Initiator', 'Profile']

class Listener(asyncore.dispatcher):

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
        conn, addr = self.accept()
        print 'Connected to %s:%s' % addr
        Session(conn, addr, self.profiles, first_channelno=2)


class Session(asynchat.async_chat):

    def __init__(self, conn, addr, profiles, first_channelno=1):
        asynchat.async_chat.__init__(self, conn)
        self.addr = addr
        self.set_terminator('\r\n')

        self.profiles = profiles
        self.channels = {0: Channel(self, 0, ManagementProfile())}
        self.channelno = cycle_through(first_channelno, 2147483647, step=2)
        self.inbuf = []
        self.header = self.payload = None

    def handle_connect(self):
        pass

    def collect_incoming_data(self, data):
        self.inbuf.append(data)

    def found_terminator(self):
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
        try:
            # Parse frame header
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
        except Exception, e:
            traceback.print_exc()

    def send_data(self, cmd, channel, msgno, more, seqno, ansno=None,
                  payload=''):
        headerbits = [cmd, channel, msgno, more and '*' or '.', seqno,
                      len(payload)]
        if cmd == 'ANS':
            assert ansno is not None
            headerbits.append(ansno)
        header = ' '.join([str(hb) for hb in headerbits])
        self.push('\r\n'.join((header, payload, 'END', '')))


class Initiator(Session):

    def __init__(self, ip, port, profiles=None):
        Session.__init__(self, None, None, profiles or {})
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connect((ip, port))


class Channel(object):
    """A specific channel of a BEEP session."""

    def __init__(self, session, channelno, profile):
        self.session = session
        self.channelno = channelno
        self.inqueue = {}
        self.outqueue = {}

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
        if seqno != self.seqno[0]: # Validate and update sequence number
            raise Exception, 'Out of sync with peer' # TODO: Be nice
        self.seqno[0] += len(payload)
        if more: # More of this message pending, so push it on the queue
            self.inqueue.setdefault(msgno, []).append(payload)
        else: # Complete message received, so handle it
            if msgno in self.inqueue.keys(): # Recombine queued messages
                payload = ''.join(self.inqueue[msgno]) + payload
                del self.inqueue[msgno]
            if cmd == 'RPY' and msgno in self.msgnos.keys():
                # Final reply using this message number, so dealloc
                del self.msgnos[msgno]
            message = None
            if payload:
                message = self.mime_parser.parsestr(payload)
            self.profile.handle_message(cmd, msgno, message)

    def _send(self, cmd, msgno, ansno=None, message=None):
        # TODO: Fragment and queue the message if necessary;
        #       First need TCP mapping (RFC 3081) for that to make real sense
        payload = ''
        if message is not None:
            payload = message.as_string()
        self.session.send_data(cmd, self.channelno, msgno, False,
                               self.seqno[1].value, payload=payload,
                               ansno=ansno)
        self.seqno[1] += len(payload)

    def send_msg(self, message):
        while True: # Find a unique message number
            msgno = self.msgno.next()
            if msgno not in self.msgnos.keys():
                break
        self.msgnos[msgno] = True # Flag the chosen message number as in use
        self._send('MSG', msgno, None, message)

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
        self._send('ANS', msgno, ansno.next(), message)

    def send_nul(self, msgno):
        self._send('NUL', msgno)


class Profile(object):
    """Abstract base class for handlers of specific BEEP profiles."""
    # TODO: This is pretty thin... would a meta-class for declarative definition
    #       of profiles work here? 

    def __init__(self):
        self.session = None
        self.channel = None

    def handle_connect(self):
        pass

    def handle_message(self, cmd, message):
        raise NotImplementedError


class ManagementProfile(Profile):
    CONTENT_TYPE = 'application/beep+xml'

    def __init__(self):
        Profile.__init__(self)
        self.state = 'init'

    def handle_connect(self):
        greeting = Element('greeting')[
            [Element('profile', uri=k) for k in self.session.profiles.keys()]
        ]
        self.channel.send_rpy(0, MIMEMessage(greeting, self.CONTENT_TYPE))

    def handle_message(self, cmd, msgno, message):
        assert message.get_content_type() == self.CONTENT_TYPE
        root = parse_xml(message.get_payload())
        if cmd == 'MSG':
            if root.name == 'start':
                print 'Start channel %s' % root.number
                for profile in root['profile']:
                    if uri in self.session.profiles.keys():
                        message = MIMEMessage(Element('profile',
                                                      uri=profile.uri),
                                              self.CONTENT_TYPE)
                        self.channel.send_rpy(msgno, message)
                        # TODO: create the channel
                        return
                # TODO: send error (unsupported profile)
            elif root.name == 'close':
                print 'Close channel %s' % root.number
                message = MIMEMessage(Element('ok'), self.CONTENT_TYPE)
                self.channel.send_rpy(msgno, message)
                # TODO: close the channel, or if channelno is 0, terminate the
                #       session... actually, that's done implicitly when the
                #       peer disconnects after receiving the <ok/>
        elif cmd == 'RPY':
            if root.name == 'greeting':
                print 'Greeting...'
                for profile in root['profile']:
                    print '  profile %s' % profile.uri
                # TODO: invoke handler handle_greeting(profiles) or something
            elif root.name == 'profile':
                # This means that the channel has been established with this
                # profile... basically a channel_start_ok message
                print 'Profile %s' % root.uri
            elif root.name == 'ok':
                # A close request for a channel has been accepted, so we can
                # close it now
                print 'OK'

    def close(self, channel=0, code=200):
        xml = Element('close', number=channel, code=code)
        self.channel.send_msg(MIMEMessage(xml, self.CONTENT_TYPE))

    def start(self, profiles):
        xml = Element('start', number=self.session.channelno.next())[
            [Element('profile', uri=uri) for uri in profiles]
        ]
        self.channel.send_msg(MIMEMessage(xml, self.CONTENT_TYPE))


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


if __name__ == '__main__':
    listener = Listener('127.0.0.1', 8000)
    try:
        asyncore.loop()
    except KeyboardInterrupt:
        pass
