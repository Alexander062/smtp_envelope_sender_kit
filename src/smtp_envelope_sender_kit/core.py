"""Parse RFC 5321 MAIL FROM and RCPT TO command arguments.

The grammar in RFC 5321 section 4.1.2 allows three shapes for the address
argument:

    Reverse-path   = Path / "<>"
    Forward-path   = Path
    Path           = "<" [ A-d-l ":" ] Mailbox ">"
    A-d-l          = At-domain *( "," At-domain )
    At-domain      = "@" Domain

A source route (the ``@host,@host:`` prefix) is syntactically valid but is
obsolete in practice and almost always rejected by relays.  This module
accepts it and records it rather than silently dropping it, so a caller can
choose to reject it.  That is the one deliberate trade-off: we are a parser,
not a policy engine.

We do not attempt full RFC 5322 mailbox parsing.  The local part and domain are
returned as written between the angle brackets (minus the source route), and
the caller can apply whatever quoting or IDN rules it needs.  Over-parsing
here is how parsers start rejecting addresses that real MTAs accept.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


class EnvelopeSyntaxError(ValueError):
    """Raised when a command argument is not a valid RFC 5321 path."""


@dataclass(frozen=True)
class EnvelopeAddress:
    """The result of parsing a MAIL FROM or RCPT TO argument.

    Attributes:
        local: The local part, exactly as it appeared, without quotes removed.
        domain: The domain, exactly as it appeared.
        source_route: The ``@host`` entries from an A-d-l prefix, in order.
            Empty when no source route was present.
        is_null: True for the null reverse-path ``<>``.  In that case
            ``local`` and ``domain`` are both empty strings.
    """

    local: str
    domain: str
    source_route: Tuple[str, ...] = field(default_factory=tuple)
    is_null: bool = False

    @property
    def address(self) -> str:
        """Return ``local@domain``, or the empty string for the null path."""
        if self.is_null:
            return ""
        return f"{self.local}@{self.domain}"

    @property
    def has_source_route(self) -> bool:
        """True when an A-d-l prefix was parsed."""
        return bool(self.source_route)


def _split_source_route(inner: str) -> Tuple[List[str], str]:
    """Split an A-d-l prefix off the front of a path body.

    The separator between the route and the mailbox is the first colon that
    appears before any '<'.  A colon inside a quoted local part cannot occur
    before the mailbox starts, so this is safe for the grammar we accept.
    """
    colon = inner.find(":")
    if colon == -1:
        return [], inner
    route_text = inner[:colon]
    mailbox = inner[colon + 1 :]
    if not route_text:
        raise EnvelopeSyntaxError("empty source route before ':'")
    if not route_text.startswith("@"):
        raise EnvelopeSyntaxError("source route must start with '@'")
    parts = route_text.split(",")
    hosts: List[str] = []
    for part in parts:
        if not part.startswith("@"):
            raise EnvelopeSyntaxError("source route entry must start with '@'")
        host = part[1:]
        if not host:
            raise EnvelopeSyntaxError("empty host in source route")
        hosts.append(host)
    return hosts, mailbox


def _parse_path(argument: str) -> EnvelopeAddress:
    """Parse the argument of MAIL FROM or RCPT TO.

    The argument must be a single path token: either ``<>`` or
    ``<[route:]mailbox>``.  Trailing ESMTP parameters are not part of this
    function; strip them first with :func:`split_parameters` if present.
    """
    if not argument:
        raise EnvelopeSyntaxError("empty argument")
    if not argument.startswith("<"):
        raise EnvelopeSyntaxError("path must start with '<'")
    if not argument.endswith(">"):
        raise EnvelopeSyntaxError("path must end with '>'")
    inner = argument[1:-1]
    if inner == "":
        return EnvelopeAddress(local="", domain="", is_null=True)

    route, mailbox = _split_source_route(inner)
    if not mailbox:
        raise EnvelopeSyntaxError("missing mailbox after source route")
    at = mailbox.find("@")
    if at == -1:
        raise EnvelopeSyntaxError("mailbox must contain '@'")
    local = mailbox[:at]
    domain = mailbox[at + 1 :]
    if not local:
        raise EnvelopeSyntaxError("empty local part")
    if not domain:
        raise EnvelopeSyntaxError("empty domain")
    return EnvelopeAddress(
        local=local,
        domain=domain,
        source_route=tuple(route),
        is_null=False,
    )


def split_parameters(argument: str) -> Tuple[str, List[str]]:
    """Split a path argument from its trailing ESMTP parameters.

    Returns ``(path, parameters)`` where ``path`` is the ``<...>`` token and
    ``parameters`` is the list of whitespace-separated tokens after it.  A
    ``>`` inside a quoted string does not terminate the path, because quoted
    local parts may legally contain it.
    """
    if not argument:
        raise EnvelopeSyntaxError("empty argument")
    if argument[0] != "<":
        raise EnvelopeSyntaxError("path must start with '<'")
    in_quotes = False
    escaped = False
    for index in range(1, len(argument)):
        ch = argument[index]
        if escaped:
            escaped = False
            continue
        if ch == "\\" and in_quotes:
            escaped = True
            continue
        if ch == '"':
            in_quotes = not in_quotes
            continue
        if ch == ">" and not in_quotes:
            path = argument[: index + 1]
            rest = argument[index + 1 :]
            params = rest.split()
            return path, params
    raise EnvelopeSyntaxError("unterminated path: missing '>'")


def parse_mail_from(argument: str) -> EnvelopeAddress:
    """Parse the argument of a ``MAIL FROM`` command.

    Accepts the bare path plus optional ESMTP parameters.  The null
    reverse-path ``<>`` is accepted and returned with ``is_null=True``.
    """
    path, _params = split_parameters(argument)
    return _parse_path(path)


def parse_rcpt_to(argument: str) -> EnvelopeAddress:
    """Parse the argument of a ``RCPT TO`` command.

    Same shape as :func:`parse_mail_from`, but ``<>`` is not a meaningful
    recipient and is rejected.
    """
    path, _params = split_parameters(argument)
    result = _parse_path(path)
    if result.is_null:
        raise EnvelopeSyntaxError("null path is not a valid recipient")
    return result
