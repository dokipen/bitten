import asyncore
import sys
import time

from bitten.util.beep import Initiator, MIMEMessage, Profile
from bitten.util.xmlio import Element, parse_xml


if __name__ == '__main__':
    host = 'localhost'
    port = 8000
    if len(sys.argv) > 1:
        host = sys.argv[1]
        if len(sys.argv) > 2:
            port = int(sys.argv[2])


    class EchoProfile(Profile):
        URI = 'http://www.eigenmagic.com/beep/ECHO'

        def handle_connect(self):
            print 'Here we are!'
            msgno = self.channel.send_msg(MIMEMessage('Hello peer!'))

        def handle_rpy(self, msgno, message):
            print message.get_payload()


    class EchoClient(Initiator):

        def handle_start_error(self, code, message):
            print>>sys.stderr, 'Error %d: %s' % (code, message)

        def handle_start_ok(self, channelno, uri):
            print 'Channel %d started for profile %s...' % (channelno, uri)
            #self.channels[channelno].send_msg(MIMEMessage('Hello'))

        def greeting_received(self, profiles):
            if EchoProfile.URI in profiles:
                self.channels[0].profile.start([EchoProfile],
                                               handle_ok=self.handle_start_ok,
                                               handle_error=self.handle_start_error)

    client = EchoClient(host, port)
    try:
        while client:
            try:
                asyncore.loop()
            except KeyboardInterrupt:
                def handle_ok():
                    raise asyncore.ExitNow, 'Session terminated'
                def handle_error(code, message):
                    print>>sys.stderr, 'Peer refused to terminate session (%d)' \
                                       % code
                client.channels[0].profile.close(handle_ok=handle_ok,
                                                 handle_error=handle_error)
                time.sleep(.2)
    except asyncore.ExitNow, e:
        print e
