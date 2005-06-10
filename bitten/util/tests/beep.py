from email.Message import Message
import unittest

from bitten.util import beep


class MockSession(object):

    def __init__(self):
        self.sent_messages = []

    def send_frame(self, cmd, channel, msgno, more, seqno, ansno=None,
                   payload=''):
        self.sent_messages.append((cmd, channel, msgno, more, seqno, ansno,
                                   payload.strip()))


class MockProfile(object):

    def __init__(self):
        self.handled_messages = []

    def handle_connect(self):
        pass

    def handle_msg(self, msgno, message):
        text = message.as_string().strip()
        self.handled_messages.append(('MSG', msgno, text))

    def handle_rpy(self, msgno, message):
        text = message.as_string().strip()
        self.handled_messages.append(('RPY', msgno, text))


class ChannelTestCase(unittest.TestCase):

    def setUp(self):
        self.session = MockSession()
        self.profile = MockProfile()

    def test_handle_single_msg_frame(self):
        """
        Verify that the channel correctly passes a single frame MSG to the
        profile.
        """
        channel = beep.Channel(self.session, 0, self.profile)
        channel.handle_frame('MSG', 0, False, 0, None, 'foo bar')
        self.assertEqual(('MSG', 0, 'foo bar'),
                         self.profile.handled_messages[0])

    def test_handle_segmented_msg_frames(self):
        """
        Verify that the channel combines two segmented messages and passed the
        recombined message to the profile.
        """
        channel = beep.Channel(self.session, 0, self.profile)
        channel.handle_frame('MSG', 0, True, 0, None, 'foo ')
        channel.handle_frame('MSG', 0, False, 4, None, 'bar')
        self.assertEqual(('MSG', 0, 'foo bar'),
                         self.profile.handled_messages[0])

    def test_send_single_frame_message(self):
        """
        Verify that the channel passes a sent message up to the session for
        transmission with the correct parameters. Also assert that the
        corresponding message number (0) is reserved.
        """
        channel = beep.Channel(self.session, 0, self.profile)
        msgno = channel.send_msg(beep.MIMEMessage('foo bar'))
        self.assertEqual(('MSG', 0, msgno, False, 0L, None, 'foo bar'),
                         self.session.sent_messages[0])
        assert msgno in channel.msgnos.keys()

    def test_send_message_msgno_inc(self):
        """
        Verify that the message number is incremented for subsequent outgoing
        messages.
        """
        channel = beep.Channel(self.session, 0, self.profile)
        msgno = channel.send_msg(beep.MIMEMessage('foo bar'))
        assert msgno == 0
        self.assertEqual(('MSG', 0, msgno, False, 0L, None, 'foo bar'),
                         self.session.sent_messages[0])
        assert msgno in channel.msgnos.keys()
        msgno = channel.send_msg(beep.MIMEMessage('foo baz'))
        assert msgno == 1
        self.assertEqual(('MSG', 0, msgno, False, 8L, None, 'foo baz'),
                         self.session.sent_messages[1])
        assert msgno in channel.msgnos.keys()

    def test_send_reply(self):
        """
        Verify that sending an ANS message is processed correctly.
        """
        channel = beep.Channel(self.session, 0, self.profile)
        channel.send_rpy(0, beep.MIMEMessage('foo bar'))
        self.assertEqual(('RPY', 0, 0, False, 0L, None, 'foo bar'),
                         self.session.sent_messages[0])

    def test_message_and_reply(self):
        """
        Verify that a message number is deallocated after a final reply has been
        received.
        """
        channel = beep.Channel(self.session, 0, self.profile)
        msgno = channel.send_msg(beep.MIMEMessage('foo bar'))
        self.assertEqual(('MSG', 0, msgno, False, 0L, None, 'foo bar'),
                         self.session.sent_messages[0])
        assert msgno in channel.msgnos.keys()
        channel.handle_frame('RPY', msgno, False, 0, None, '42')
        self.assertEqual(('RPY', msgno, '42'), self.profile.handled_messages[0])
        assert msgno not in channel.msgnos.keys()

    def test_send_error(self):
        """
        Verify that sending an ERR message is processed correctly.
        """
        channel = beep.Channel(self.session, 0, self.profile)
        channel.send_err(0, beep.MIMEMessage('oops'))
        self.assertEqual(('ERR', 0, 0, False, 0L, None, 'oops'),
                         self.session.sent_messages[0])

    def test_send_answers(self):
        """
        Verify that sending an ANS message is processed correctly.
        """
        channel = beep.Channel(self.session, 0, self.profile)
        ansno = channel.send_ans(0, beep.MIMEMessage('foo bar'))
        assert ansno == 0
        self.assertEqual(('ANS', 0, 0, False, 0L, ansno, 'foo bar'),
                         self.session.sent_messages[0])
        assert 0 in channel.ansnos.keys()
        ansno = channel.send_ans(0, beep.MIMEMessage('foo baz'))
        assert ansno == 1
        self.assertEqual(('ANS', 0, 0, False, 8L, ansno, 'foo baz'),
                         self.session.sent_messages[1])
        assert 0 in channel.ansnos.keys()
        channel.send_nul(0)
        self.assertEqual(('NUL', 0, 0, False, 16L, None, ''),
                         self.session.sent_messages[2])
        assert 0 not in channel.ansnos.keys()


def suite():
    return unittest.makeSuite(ChannelTestCase, 'test')

if __name__ == '__main__':
	unittest.main()
