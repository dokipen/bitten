import asyncore
import sys
import time

from bitten.util.beep import Initiator, MIMEMessage, Profile
from bitten.util.xmlio import Element, parse_xml


class StdinChannel(asyncore.file_dispatcher):

    def __init__(self, handle_read):
        asyncore.file_dispatcher.__init__(self, sys.stdin.fileno())
        self.read_handler = handle_read

    def readable(self):
        return True

    def handle_read(self):
        data = self.recv(8192)
        self.read_handler(data)

    def writable(self):
        return False


class EchoProfile(Profile):
    URI = 'http://beepcore.org/beep/ECHO'

    def handle_rpy(self, msgno, message):
        print '\x1b[31m' + message.get_payload().rstrip() + '\x1b[0m'


class EchoClient(Initiator):

    channel = None

    def greeting_received(self, profiles):
        def handle_ok(channelno, uri):
            print 'Channel %d started for profile %s...' % (channelno, uri)
            self.channel = channelno
        def handle_error(code, message):
            print>>sys.stderr, 'Error %d: %s' % (code, message)
        if EchoProfile.URI in profiles:
            self.channels[0].profile.send_start([EchoProfile],
                                                handle_ok=handle_ok,
                                                handle_error=handle_error)


if __name__ == '__main__':
    host = 'localhost'
    port = 8000
    if len(sys.argv) > 1:
        host = sys.argv[1]
        if len(sys.argv) > 2:
            port = int(sys.argv[2])

    client = EchoClient(host, port)
    def handle_input(data):
        message = MIMEMessage(data, 'text/plain')
        client.channels[client.channel].send_msg(message)
    stdin = StdinChannel(handle_input)
    try:
        while client:
            try:
                asyncore.loop()
            except KeyboardInterrupt:
                mgmt = client.channels[0].profile
                def handle_ok():
                    raise asyncore.ExitNow, 'Session terminated'
                def handle_error(code, message):
                    print>>sys.stderr, \
                        'Peer refused to terminate session (%d): %s' \
                        % (code, message)
                mgmt.send_close(client.channel)
                mgmt.send_close(handle_ok=handle_ok, handle_error=handle_error)
                time.sleep(.25)
    except asyncore.ExitNow, e:
        print e
