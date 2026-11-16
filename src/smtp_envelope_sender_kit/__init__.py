"""Public API for smtp_envelope_sender_kit.

Only the parser and its result type are exported; the tokenizer is an
implementation detail that callers should not depend on.
"""

from .core import EnvelopeAddress, parse_mail_from, parse_rcpt_to

__all__ = ["EnvelopeAddress", "parse_mail_from", "parse_rcpt_to"]
