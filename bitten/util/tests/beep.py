import logging
import unittest

from bitten.util import beep, xmlio


class MockSession(beep.Initiator):

    def __init__(self):
        self.closed = False
        self.profiles = {}
        self.sent_messages = []
        self.channelno = beep.cycle_through(1, 2147483647, step=2)
        self.channels = {0: beep.Channel(self, 0,
                                         beep.ManagementProfileHandler)}
        del self.sent_messages[0] # Clear out the management greeting
        self.channels[0].seqno = [beep.SerialNumber(), beep.SerialNumber()]

    def close(self):
        self.closed = True

    def send_data_frame(self, cmd, channel, msgno, more, seqno, ansno=None,
                        payload=''):
        assert not self.closed
        self.sent_messages.append((cmd, channel, msgno, more, seqno, ansno,
                                   payload.strip()))


class MockProfileHandler(object):
    URI = 'http://example.com/mock'

    def __init__(self, channel):
        self.handled_messages = []
        self.init_elem = None

    def handle_connect(self, init_elem=None):
        self.init_elem = init_elem

    def handle_disconnect(self):
        pass

    def handle_msg(self, msgno, message):
        text = message.as_string().strip()
        self.handled_messages.append(('MSG', msgno, text, None))

    def handle_rpy(self, msgno, message):
        text = message.as_string().strip()
        self.handled_messages.append(('RPY', msgno, text, None))

    def handle_err(self, msgno, message):
        text = message.as_string().strip()
        self.handled_messages.append(('ERR', msgno, text, None))

    def handle_ans(self, msgno, ansno, message):
        text = message.as_string().strip()
        self.handled_messages.append(('ANS', msgno, text, ansno))

    def handle_nul(self, msgno):
        self.handled_messages.append(('NUL', msgno, '', None))


class ChannelTestCase(unittest.TestCase):

    def setUp(self):
        self.session = MockSession()

    def test_handle_single_msg_frame(self):
        """
        Verify that the channel correctly passes a single frame MSG to the
        profile.
        """
        channel = beep.Channel(self.session, 0, MockProfileHandler)
        channel.handle_data_frame('MSG', 0, False, 0, None, 'foo bar')
        self.assertEqual(('MSG', 0, 'foo bar', None),
                         channel.profile.handled_messages[0])

    def test_handle_segmented_msg_frames(self):
        """
        Verify that the channel combines two segmented messages and passed the
        recombined message to the profile.
        """
        channel = beep.Channel(self.session, 0, MockProfileHandler)
        channel.handle_data_frame('MSG', 0, True, 0, None, 'foo ')
        channel.handle_data_frame('MSG', 0, False, 4, None, 'bar')
        self.assertEqual(('MSG', 0, 'foo bar', None),
                         channel.profile.handled_messages[0])

    def test_handle_out_of_sync_frame(self):
        """
        Verify that the channel detects out-of-sync frames and bails.
        """
        channel = beep.Channel(self.session, 0, MockProfileHandler)
        channel.handle_data_frame('MSG', 0, False, 0L, None, 'foo bar')
        # The next sequence number should be 8; send 12 instead
        self.assertRaises(beep.ProtocolError, channel.handle_data_frame, 'MSG',
                          0, False, 12L, None, 'foo baz')

    def test_send_single_frame_message(self):
        """
        Verify that the channel passes a sent message up to the session for
        transmission with the correct parameters. Also assert that the
        corresponding message number (0) is reserved.
        """
        channel = beep.Channel(self.session, 0, MockProfileHandler)
        msgno = channel.send_msg(beep.Payload('foo bar', None))
        self.assertEqual(('MSG', 0, msgno, False, 0L, None, 'foo bar'),
                         self.session.sent_messages[0])
        assert msgno in channel.msgnos

    def test_send_frames_seqno_incrementing(self):
        """
        Verify that the sequence numbers of outgoing frames are incremented as
        expected.
        """
        channel = beep.Channel(self.session, 0, MockProfileHandler)
        channel.send_msg(beep.Payload('foo bar', None))
        channel.send_rpy(0, beep.Payload('nil', None))
        self.assertEqual(('MSG', 0, 0, False, 0L, None, 'foo bar'),
                         self.session.sent_messages[0])
        self.assertEqual(('RPY', 0, 0, False, 8L, None, 'nil'),
                         self.session.sent_messages[1])

    def test_send_message_msgno_incrementing(self):
        """
        Verify that the message number is incremented for subsequent outgoing
        messages.
        """
        channel = beep.Channel(self.session, 0, MockProfileHandler)
        msgno = channel.send_msg(beep.Payload('foo bar', None))
        assert msgno == 0
        self.assertEqual(('MSG', 0, msgno, False, 0L, None, 'foo bar'),
                         self.session.sent_messages[0])
        assert msgno in channel.msgnos
        msgno = channel.send_msg(beep.Payload('foo baz', None))
        assert msgno == 1
        self.assertEqual(('MSG', 0, msgno, False, 8L, None, 'foo baz'),
                         self.session.sent_messages[1])
        assert msgno in channel.msgnos

    def test_send_reply(self):
        """
        Verify that sending an ANS message is processed correctly.
        """
        channel = beep.Channel(self.session, 0, MockProfileHandler)
        channel.send_rpy(0, beep.Payload('foo bar', None))
        self.assertEqual(('RPY', 0, 0, False, 0L, None, 'foo bar'),
                         self.session.sent_messages[0])

    def test_message_and_reply(self):
        """
        Verify that a message number is deallocated after a final "RPY" reply
        has been received.
        """
        channel = beep.Channel(self.session, 0, MockProfileHandler)
        msgno = channel.send_msg(beep.Payload('foo bar', None))
        self.assertEqual(('MSG', 0, msgno, False, 0L, None, 'foo bar'),
                         self.session.sent_messages[0])
        assert msgno in channel.msgnos
        channel.handle_data_frame('RPY', msgno, False, 0, None, '42')
        self.assertEqual(('RPY', msgno, '42', None),
                         channel.profile.handled_messages[0])
        assert msgno not in channel.msgnos

    def test_message_and_error(self):
        """
        Verify that a message number is deallocated after a final "ERR" reply
        has been received.
        """
        channel = beep.Channel(self.session, 0, MockProfileHandler)
        msgno = channel.send_msg(beep.Payload('foo bar', None))
        self.assertEqual(('MSG', 0, msgno, False, 0L, None, 'foo bar'),
                         self.session.sent_messages[0])
        assert msgno in channel.msgnos
        channel.handle_data_frame('ERR', msgno, False, 0, None, '42')
        self.assertEqual(('ERR', msgno, '42', None),
                         channel.profile.handled_messages[0])
        assert msgno not in channel.msgnos

    def test_message_and_ans_nul(self):
        """
        Verify that a message number is deallocated after a final "NUL" reply
        has been received.
        """
        channel = beep.Channel(self.session, 0, MockProfileHandler)
        msgno = channel.send_msg(beep.Payload('foo bar', None))
        self.assertEqual(('MSG', 0, msgno, False, 0L, None, 'foo bar'),
                         self.session.sent_messages[0])
        assert msgno in channel.msgnos
        channel.handle_data_frame('ANS', msgno, False, 0, 0, '42')
        self.assertEqual(('ANS', msgno, '42', 0),
                         channel.profile.handled_messages[0])
        assert msgno in channel.msgnos
        channel.handle_data_frame('NUL', msgno, False, 2, None, '42')
        self.assertEqual(('NUL', msgno, '', None),
                         channel.profile.handled_messages[1])
        assert msgno not in channel.msgnos

    def test_send_error(self):
        """
        Verify that sending an ERR message is processed correctly.
        """
        channel = beep.Channel(self.session, 0, MockProfileHandler)
        channel.send_err(0, beep.Payload('oops', None))
        self.assertEqual(('ERR', 0, 0, False, 0L, None, 'oops'),
                         self.session.sent_messages[0])

    def test_send_answers(self):
        """
        Verify that sending an ANS message is processed correctly.
        """
        channel = beep.Channel(self.session, 0, MockProfileHandler)
        ansno = channel.send_ans(0, beep.Payload('foo bar', None))
        assert ansno == 0
        self.assertEqual(('ANS', 0, 0, False, 0L, ansno, 'foo bar'),
                         self.session.sent_messages[0])
        assert 0 in channel.ansnos
        ansno = channel.send_ans(0, beep.Payload('foo baz', None))
        assert ansno == 1
        self.assertEqual(('ANS', 0, 0, False, 8L, ansno, 'foo baz'),
                         self.session.sent_messages[1])
        assert 0 in channel.ansnos
        channel.send_nul(0)
        self.assertEqual(('NUL', 0, 0, False, 16L, None, ''),
                         self.session.sent_messages[2])
        assert 0 not in channel.ansnos


class ManagementProfileHandlerTestCase(unittest.TestCase):

    def setUp(self):
        self.session = MockSession()
        self.channel = self.session.channels[0]
        self.profile = self.channel.profile

    def test_send_greeting(self):
        """
        Verify that the management profile sends a greeting reply when
        initialized.
        """
        self.profile.handle_connect()
        self.assertEqual(1, len(self.session.sent_messages))
        xml = xmlio.Element('greeting')
        message = beep.Payload(xml).as_string()
        self.assertEqual(('RPY', 0, 0, False, 0, None, message),
                         self.session.sent_messages[0])

    def test_send_greeting_with_profile(self):
        """
        Verify that the management profile sends a greeting with a list of
        supported profiles reply when initialized.
        """
        self.session.profiles[MockProfileHandler.URI] = MockProfileHandler
        self.profile.handle_connect()
        self.assertEqual(1, len(self.session.sent_messages))
        xml = xmlio.Element('greeting')[
            xmlio.Element('profile', uri=MockProfileHandler.URI)
        ]
        message = beep.Payload(xml).as_string()
        self.assertEqual(('RPY', 0, 0, False, 0, None, message),
                         self.session.sent_messages[0])

    def test_handle_greeting(self):
        """
        Verify that the management profile calls the greeting_received() method
        of the initiator session.
        """
        def greeting_received(profiles):
            greeting_received.called = True
            self.assertEqual(['test'], profiles)
        greeting_received.called = False
        self.session.greeting_received = greeting_received
        xml = xmlio.Element('greeting')[xmlio.Element('profile', uri='test')]
        message = beep.Payload(xml).as_string()
        self.channel.handle_data_frame('RPY', 0, False, 0L, None, message)
        assert greeting_received.called

    def test_handle_start(self):
        self.session.profiles[MockProfileHandler.URI] = MockProfileHandler
        xml = xmlio.Element('start', number=2)[
            xmlio.Element('profile', uri=MockProfileHandler.URI),
            xmlio.Element('profile', uri='http://example.com/bogus')
        ]
        self.profile.handle_msg(0, beep.Payload(xml))

        assert 2 in self.session.channels
        xml = xmlio.Element('profile', uri=MockProfileHandler.URI)
        message = beep.Payload(xml).as_string()
        self.assertEqual(('RPY', 0, 0, False, 0, None, message),
                         self.session.sent_messages[0])

    def test_handle_start_unsupported_profile(self):
        self.session.profiles[MockProfileHandler.URI] = MockProfileHandler
        xml = xmlio.Element('start', number=2)[
            xmlio.Element('profile', uri='http://example.com/foo'),
            xmlio.Element('profile', uri='http://example.com/bar')
        ]
        self.profile.handle_msg(0, beep.Payload(xml))

        assert 2 not in self.session.channels
        xml = xmlio.Element('error', code=550)[
            'None of the requested profiles is supported'
        ]
        message = beep.Payload(xml).as_string()
        self.assertEqual(('ERR', 0, 0, False, 0, None, message),
                         self.session.sent_messages[0])

    def test_handle_start_channel_in_use(self):
        self.session.channels[2] = beep.Channel(self.session, 2,
                                                MockProfileHandler)
        orig_profile = self.session.channels[2].profile
        self.session.profiles[MockProfileHandler.URI] = MockProfileHandler
        xml = xmlio.Element('start', number=2)[
            xmlio.Element('profile', uri=MockProfileHandler.URI)
        ]
        self.profile.handle_msg(0, beep.Payload(xml))

        assert self.session.channels[2].profile is orig_profile
        xml = xmlio.Element('error', code=550)['Channel already in use']
        message = beep.Payload(xml).as_string()
        self.assertEqual(('ERR', 0, 0, False, 0, None, message),
                         self.session.sent_messages[0])

    def test_handle_close(self):
        self.session.channels[1] = beep.Channel(self.session, 1,
                                                MockProfileHandler)
        xml = xmlio.Element('close', number=1, code=200)
        self.profile.handle_msg(0, beep.Payload(xml))

        assert 1 not in self.session.channels
        xml = xmlio.Element('ok')
        message = beep.Payload(xml).as_string()
        self.assertEqual(('RPY', 0, 0, False, 0, None, message),
                         self.session.sent_messages[0])

    def test_handle_close_session(self):
        xml = xmlio.Element('close', number=0, code=200)
        self.profile.handle_msg(0, beep.Payload(xml))

        assert 1 not in self.session.channels
        xml = xmlio.Element('ok')
        message = beep.Payload(xml).as_string()
        self.assertEqual(('RPY', 0, 0, False, 0, None, message),
                         self.session.sent_messages[0])
        assert self.session.closed

    def test_handle_close_channel_not_open(self):
        xml = xmlio.Element('close', number=1, code=200)
        self.profile.handle_msg(0, beep.Payload(xml))

        xml = xmlio.Element('error', code=550)['Channel not open']
        message = beep.Payload(xml).as_string()
        self.assertEqual(('ERR', 0, 0, False, 0, None, message),
                         self.session.sent_messages[0])

    def test_handle_close_channel_busy(self):
        self.session.channels[1] = beep.Channel(self.session, 1,
                                                MockProfileHandler)
        self.session.channels[1].send_msg(beep.Payload('test'))
        assert self.session.channels[1].msgnos

        xml = xmlio.Element('close', number=1, code=200)
        self.profile.handle_msg(0, beep.Payload(xml))

        xml = xmlio.Element('error', code=550)['Channel waiting for replies']
        message = beep.Payload(xml).as_string()
        self.assertEqual(('ERR', 0, 0, False, 0, None, message),
                         self.session.sent_messages[1])

    def test_handle_close_session_busy(self):
        self.session.channels[1] = beep.Channel(self.session, 1,
                                                MockProfileHandler)

        xml = xmlio.Element('close', number=0, code=200)
        self.profile.handle_msg(0, beep.Payload(xml))

        xml = xmlio.Element('error', code=550)['Other channels still open']
        message = beep.Payload(xml).as_string()
        self.assertEqual(('ERR', 0, 0, False, 0, None, message),
                         self.session.sent_messages[0])

    def test_send_error(self):
        """
        Verify that a negative reply is sent as expected.
        """
        self.profile.send_error(0, 521, 'ouch')
        xml = xmlio.Element('error', code=521)['ouch']
        message = beep.Payload(xml).as_string()
        self.assertEqual(('ERR', 0, 0, False, 0, None, message),
                         self.session.sent_messages[0])

    def test_send_start(self):
        """
        Verify that a <start> request is sent correctly.
        """
        self.profile.send_start([MockProfileHandler])
        xml = xmlio.Element('start', number="1")[
            xmlio.Element('profile', uri=MockProfileHandler.URI)
        ]
        message = beep.Payload(xml).as_string()
        self.assertEqual(('MSG', 0, 0, False, 0, None, message),
                         self.session.sent_messages[0])

    def test_send_start_ok(self):
        """
        Verify that a positive reply to a <start> request is handled correctly,
        and the channel is created.
        """
        self.profile.send_start([MockProfileHandler])
        xml = xmlio.Element('profile', uri=MockProfileHandler.URI)
        message = beep.Payload(xml).as_string()
        self.channel.handle_data_frame('RPY', 0, False, 0L, None, message)
        assert isinstance(self.session.channels[1].profile, MockProfileHandler)

    def test_send_start_error(self):
        """
        Verify that a negative reply to a <close> request is handled correctly,
        and no channel gets created.
        """
        self.profile.send_start([MockProfileHandler])
        xml = xmlio.Element('error', code=500)['ouch']
        message = beep.Payload(xml).as_string()
        self.channel.handle_data_frame('ERR', 0, False, 0L, None, message)
        assert 1 not in self.session.channels

    def test_send_start_ok_with_callback(self):
        """
        Verify that user-supplied callback for positive replies is invoked
        when a <profile> reply is received in response to a <start> request.
        """
        def handle_ok(channelno, profile_uri):
            self.assertEqual(1, channelno)
            self.assertEqual(MockProfileHandler.URI, profile_uri)
            handle_ok.called = True
        handle_ok.called = False
        def handle_error(code, text):
            handle_error.called = True
        handle_error.called = False
        self.profile.send_start([MockProfileHandler], handle_ok=handle_ok,
                                handle_error=handle_error)

        xml = xmlio.Element('profile', uri=MockProfileHandler.URI)
        message = beep.Payload(xml).as_string()
        self.channel.handle_data_frame('RPY', 0, False, 0L, None, message)
        assert isinstance(self.session.channels[1].profile, MockProfileHandler)
        assert handle_ok.called
        assert not handle_error.called

    def test_send_start_error_with_callback(self):
        """
        Verify that user-supplied callback for negative replies is invoked
        when an error is received in response to a <start> request.
        """
        def handle_ok(channelno, profile_uri):
            handle_ok.called = True
        handle_ok.called = False
        def handle_error(code, text):
            self.assertEqual(500, code)
            self.assertEqual('ouch', text)
            handle_error.called = True
        handle_error.called = False
        self.profile.send_start([MockProfileHandler], handle_ok=handle_ok,
                                handle_error=handle_error)

        xml = xmlio.Element('error', code=500)['ouch']
        message = beep.Payload(xml).as_string()
        self.channel.handle_data_frame('ERR', 0, False, 0L, None, message)
        assert 1 not in self.session.channels
        assert not handle_ok.called
        assert handle_error.called

    def test_send_close(self):
        """
        Verify that a <close> request is sent correctly.
        """
        self.profile.send_close(1, code=200)
        xml = xmlio.Element('close', number=1, code=200)
        message = beep.Payload(xml).as_string()
        self.assertEqual(('MSG', 0, 0, False, 0, None, message),
                         self.session.sent_messages[0])

    def test_send_close_ok(self):
        """
        Verify that a positive reply to a <close> request is handled correctly,
        and the channel is closed.
        """
        self.session.channels[1] = beep.Channel(self.session, 1,
                                                MockProfileHandler)
        self.profile.send_close(1, code=200)

        xml = xmlio.Element('ok')
        message = beep.Payload(xml).as_string()
        self.channel.handle_data_frame('RPY', 0, False, 0L, None, message)
        assert 1 not in self.session.channels

    def test_send_close_session_ok(self):
        """
        Verify that a positive reply to a <close> request is handled correctly,
        and the channel is closed.
        """
        self.profile.send_close(0, code=200)

        xml = xmlio.Element('ok')
        message = beep.Payload(xml).as_string()
        self.channel.handle_data_frame('RPY', 0, False, 0L, None, message)
        assert 0 not in self.session.channels
        assert self.session.closed

    def test_send_close_error(self):
        """
        Verify that a negative reply to a <close> request is handled correctly,
        and the channel stays open.
        """
        self.session.channels[1] = beep.Channel(self.session, 1,
                                                MockProfileHandler)
        self.profile.send_close(1, code=200)

        xml = xmlio.Element('error', code=500)['ouch']
        message = beep.Payload(xml).as_string()
        self.channel.handle_data_frame('ERR', 0, False, 0L, None, message)
        assert 1 in self.session.channels

    def test_send_close_ok_with_callback(self):
        """
        Verify that user-supplied callback for positive replies is invoked
        when an <ok> reply is received in response to a <close> request.
        """
        self.session.channels[1] = beep.Channel(self.session, 1,
                                                MockProfileHandler)
        def handle_ok():
            handle_ok.called = True
        handle_ok.called = False
        def handle_error(code, text):
            handle_error.called = True
        handle_error.called = False
        self.profile.send_close(1, code=200, handle_ok=handle_ok,
                                handle_error=handle_error)

        xml = xmlio.Element('profile', uri=MockProfileHandler.URI)
        message = beep.Payload(xml).as_string()
        self.channel.handle_data_frame('RPY', 0, False, 0L, None, message)
        assert 1 not in self.session.channels
        assert handle_ok.called
        assert not handle_error.called

    def test_send_close_error_with_callback(self):
        """
        Verify that user-supplied callback for negative replies is invoked
        when an error is received in response to a <close> request.
        """
        self.session.channels[1] = beep.Channel(self.session, 1,
                                                MockProfileHandler)
        def handle_ok(channelno, profile_uri):
            handle_ok.called = True
        handle_ok.called = False
        def handle_error(code, text):
            self.assertEqual(500, code)
            self.assertEqual('ouch', text)
            handle_error.called = True
        handle_error.called = False
        self.profile.send_close(1, code=200, handle_ok=handle_ok,
                                handle_error=handle_error)

        xml = xmlio.Element('error', code=500)['ouch']
        message = beep.Payload(xml).as_string()
        self.channel.handle_data_frame('ERR', 0, False, 0L, None, message)
        assert 1 in self.session.channels
        assert not handle_ok.called
        assert handle_error.called


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(ChannelTestCase, 'test'))
    suite.addTest(unittest.makeSuite(ManagementProfileHandlerTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
