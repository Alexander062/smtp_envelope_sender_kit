# smtp_envelope_sender_kit

Parses RFC 5321 `MAIL FROM` and `RCPT TO` command arguments, including ESMTP parameters and the obsolete source-route syntax.

```python
from smtp_envelope_sender_kit import parse_mail_from, parse_rcpt_to

sender = parse_mail_from("<alice@example.org> SIZE=2048")
sender.address          # 'alice@example.org'
sender.local            # 'alice'
sender.domain           # 'example.org'
sender.is_null          # False

recipient = parse_rcpt_to("<@relay.example:bob@example.net>")
recipient.source_route  # ('relay.example',)
recipient.has_source_route  # True

null_sender = parse_mail_from("<>")
null_sender.is_null     # True
null_sender.address     # ''
```

## Why this exists

SMTP servers and test harnesses need to pull the envelope address out of a command line without losing the parts that matter for policy: the null reverse-path used by bounce messages, the ESMTP parameters that follow the path, and the source-route prefix that RFC 5321 still permits but almost every relay rejects. Reimplementing that split in every project leads to subtly different rules.

The trade-off here is deliberate: the parser validates the *shape* of the path (angle brackets, an `@`, a non-empty local part and domain, a well-formed source route) but it does **not** normalise or validate the mailbox itself. Quoted local parts are returned with their quotes and backslashes intact, and the domain is returned verbatim. That means an address like `"weird>name"@example.com` round-trips exactly, and internationalised domains are left for the caller to handle. Rejecting addresses that a real MTA would accept is worse than returning them unchanged.

## The awkward edge

A `>` inside a quoted local part does not end the path. `parse_mail_from('<"a>b"@example.com> SIZE=5')` returns a local part of `"a>b"` and ignores `SIZE=5`; a naive `str.split('>')` would truncate the address. The same applies to escaped quotes inside quoted strings.

## API

The package exports four names:

- `parse_mail_from(argument: str) -> EnvelopeAddress` — parses a `MAIL FROM` argument. Accepts `<>` and returns `is_null=True` for it.
- `parse_rcpt_to(argument: str) -> EnvelopeAddress` — parses a `RCPT TO` argument. Rejects `<>` with `EnvelopeSyntaxError`, because a null recipient is not meaningful.
- `EnvelopeAddress` — a frozen dataclass with fields `local`, `domain`, `source_route` (a tuple of hostnames), and `is_null`, plus the properties `address` and `has_source_route`.
- `EnvelopeSyntaxError` — a subclass of `ValueError` raised for malformed input.

`split_parameters(argument)` is also available from `smtp_envelope_sender_kit.core` for callers that need the path and the ESMTP parameter tokens separately.

## Running the tests

```
PYTHONPATH=src python -m unittest discover -s tests
```
