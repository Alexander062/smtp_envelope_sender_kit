import unittest

from smtp_envelope_sender_kit import (
    EnvelopeAddress,
    parse_mail_from,
    parse_rcpt_to,
)
from smtp_envelope_sender_kit.core import EnvelopeSyntaxError, split_parameters


class TestParseMailFrom(unittest.TestCase):
    def test_plain_address(self):
        result = parse_mail_from("<alice@example.org>")
        self.assertEqual(result.local, "alice")
        self.assertEqual(result.domain, "example.org")
        self.assertEqual(result.source_route, ())
        self.assertFalse(result.is_null)
        self.assertEqual(result.address, "alice@example.org")

    def test_null_reverse_path(self):
        result = parse_mail_from("<>")
        self.assertTrue(result.is_null)
        self.assertEqual(result.local, "")
        self.assertEqual(result.domain, "")
        self.assertEqual(result.address, "")
        self.assertFalse(result.has_source_route)

    def test_esmtp_parameters_are_ignored(self):
        result = parse_mail_from("<bob@example.net> SIZE=1024 BODY=8BITMIME")
        self.assertEqual(result.address, "bob@example.net")

    def test_source_route_is_recorded(self):
        result = parse_mail_from("<@relay1.example,@relay2.example:carol@example.com>")
        self.assertEqual(result.local, "carol")
        self.assertEqual(result.domain, "example.com")
        self.assertEqual(result.source_route, ("relay1.example", "relay2.example"))
        self.assertTrue(result.has_source_route)

    def test_quoted_local_part_with_gt(self):
        result = parse_mail_from('<"weird>name"@example.com> SIZE=10')
        self.assertEqual(result.local, '"weird>name"')
        self.assertEqual(result.domain, "example.com")

    def test_quoted_local_part_with_escaped_quote(self):
        result = parse_mail_from('<"a\\"b"@example.com>')
        self.assertEqual(result.local, '"a\\"b"')
        self.assertEqual(result.domain, "example.com")

    def test_missing_angle_brackets(self):
        with self.assertRaises(EnvelopeSyntaxError):
            parse_mail_from("alice@example.org")

    def test_unterminated_path(self):
        with self.assertRaises(EnvelopeSyntaxError):
            parse_mail_from("<alice@example.org")

    def test_missing_at_sign(self):
        with self.assertRaises(EnvelopeSyntaxError):
            parse_mail_from("<alice>")

    def test_empty_local_part(self):
        with self.assertRaises(EnvelopeSyntaxError):
            parse_mail_from("<@example.org>")

    def test_empty_domain(self):
        with self.assertRaises(EnvelopeSyntaxError):
            parse_mail_from("<alice@>")

    def test_empty_source_route_entry(self):
        with self.assertRaises(EnvelopeSyntaxError):
            parse_mail_from("<@relay1.example,,carol@example.com>")

    def test_source_route_without_mailbox(self):
        with self.assertRaises(EnvelopeSyntaxError):
            parse_mail_from("<@relay1.example:>")


class TestParseRcptTo(unittest.TestCase):
    def test_plain_address(self):
        result = parse_rcpt_to("<dave@example.com>")
        self.assertEqual(result.address, "dave@example.com")

    def test_null_path_is_rejected(self):
        with self.assertRaises(EnvelopeSyntaxError):
            parse_rcpt_to("<>")

    def test_source_route_is_recorded(self):
        result = parse_rcpt_to("<@relay.example:erin@example.com>")
        self.assertEqual(result.source_route, ("relay.example",))
        self.assertEqual(result.address, "erin@example.com")


class TestSplitParameters(unittest.TestCase):
    def test_no_parameters(self):
        path, params = split_parameters("<a@b>")
        self.assertEqual(path, "<a@b>")
        self.assertEqual(params, [])

    def test_parameters(self):
        path, params = split_parameters("<a@b> SIZE=5 BODY=7BIT")
        self.assertEqual(path, "<a@b>")
        self.assertEqual(params, ["SIZE=5", "BODY=7BIT"])

    def test_gt_inside_quotes_does_not_end_path(self):
        path, params = split_parameters('<"x>y"@b> SMTPUTF8')
        self.assertEqual(path, '<"x>y"@b>')
        self.assertEqual(params, ["SMTPUTF8"])

    def test_unterminated(self):
        with self.assertRaises(EnvelopeSyntaxError):
            split_parameters("<a@b")


class TestEnvelopeAddress(unittest.TestCase):
    def test_has_source_route_false_for_plain(self):
        addr = EnvelopeAddress(local="a", domain="b")
        self.assertFalse(addr.has_source_route)
        self.assertEqual(addr.address, "a@b")

    def test_has_source_route_true(self):
        addr = EnvelopeAddress(local="a", domain="b", source_route=("r",))
        self.assertTrue(addr.has_source_route)


if __name__ == "__main__":
    unittest.main()
