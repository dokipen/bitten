from email.Message import Message
import unittest

from bitten.util import beep


class MockSession(object):

    def __init__(self):
        self.sent_messages = []

    def send_data(self, cmd, channel, msgno, more, seqno, ansno=None,
                  payload=''):
        self.sent_messages.append((cmd, channel, msgno, more, seqno, ansno,
                                   payload.strip()))


class MockProfile(object):

    def __init__(self):
        self.handled_messages = []

    def handle_connect(self):
        pass

    def handle_message(self, cmd, msgno, message):
        self.handled_messages.append((cmd, msgno, message.as_string().strip()))


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
        channel.send_msg(beep.MIMEMessage('foo bar'))
        self.assertEqual(('MSG', 0, 0, False, 0L, None, 'foo bar'),
                         self.session.sent_messages[0])
        assert 0 in channel.msgnos.keys()

    def test_send_message_msgno_inc(self):
        """
        Verify that the message number is incremented for subsequent outgoing
        messages.
        """
        channel = beep.Channel(self.session, 0, self.profile)
        channel.send_msg(beep.MIMEMessage('foo bar'))
        self.assertEqual(('MSG', 0, 0, False, 0L, None, 'foo bar'),
                         self.session.sent_messages[0])
        assert 0 in channel.msgnos.keys()
        channel.send_msg(beep.MIMEMessage('foo baz'))
        self.assertEqual(('MSG', 0, 1, False, 8L, None, 'foo baz'),
                         self.session.sent_messages[1])
        assert 1 in channel.msgnos.keys()

    def test_message_and_reply(self):
        """
        Verify that a message number is deallocated after a final reply has been
        received.
        """
        channel = beep.Channel(self.session, 0, self.profile)
        channel.send_msg(beep.MIMEMessage('foo bar'))
        self.assertEqual(('MSG', 0, 0, False, 0L, None, 'foo bar'),
                         self.session.sent_messages[0])
        assert 0 in channel.msgnos.keys()
        channel.handle_frame('RPY', 0, False, 0, None, '42')
        self.assertEqual(('RPY', 0, '42'), self.profile.handled_messages[0])
        assert 0 not in channel.msgnos.keys()

    def test_send_answer(self):
        """
        Verify that sending an ANS message is processed correctly.
        """
        channel = beep.Channel(self.session, 0, self.profile)
        channel.send_ans(0, beep.MIMEMessage('foo bar'))
        self.assertEqual(('ANS', 0, 0, False, 0L, 0, 'foo bar'),
                         self.session.sent_messages[0])
        channel.send_ans(0, beep.MIMEMessage('foo baz'))
        self.assertEqual(('ANS', 0, 0, False, 8L, 1, 'foo baz'),
                         self.session.sent_messages[1])


def suite():
    return unittest.makeSuite(ChannelTestCase, 'test')

if __name__ == '__main__':
	unittest.main()
