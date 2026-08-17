"""Known-sender reminder templates — run before the generic LLM extract.

Flights stay out of this module (separate FEATURES item). Matching is linear
string work only so CodeQL does not treat inbox text as a ReDoS sink.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.gateways.google_gmail_gateway import GmailMessage

if TYPE_CHECKING:
    from app.services.email import SuggestedReminderItem

_PACKAGE_CUES = (
    "delivered",
    "out for delivery",
    "shipped",
    "arriving",
    "has shipped",
    "on the way",
    "package",
    "your order",
)
_RESERVATION_CUES = (
    "reservation",
    "booking confirmed",
    "table for",
    "your booking",
    "confirmed for",
)
_APPOINTMENT_CUES = (
    "appointment",
    "scheduled",
    "you are booked",
    "calendar invite",
    "meeting with",
)


@dataclass(frozen=True)
class _SenderKind:
    label: str
    kind: str
    domains: tuple[str, ...]
    cues: tuple[str, ...]


_SENDERS: tuple[_SenderKind, ...] = (
    _SenderKind("Amazon", "package", ("amazon.com", "amazon.co.uk", "amazon.ca"), _PACKAGE_CUES),
    _SenderKind("UPS", "package", ("ups.com",), _PACKAGE_CUES),
    _SenderKind("FedEx", "package", ("fedex.com",), _PACKAGE_CUES),
    _SenderKind("USPS", "package", ("usps.com",), _PACKAGE_CUES),
    _SenderKind("DHL", "package", ("dhl.com", "dhl.de"), _PACKAGE_CUES),
    _SenderKind(
        "OpenTable",
        "reservation",
        ("opentable.com", "opentablemail.com"),
        _RESERVATION_CUES,
    ),
    _SenderKind("Resy", "reservation", ("resy.com",), _RESERVATION_CUES),
    _SenderKind("Tock", "reservation", ("exploretock.com",), _RESERVATION_CUES),
    _SenderKind("Calendly", "appointment", ("calendly.com",), _APPOINTMENT_CUES),
)


def email_domain(from_address: str) -> str:
    """Host after the last ``@``, stripped of ``>`` / trailing junk."""
    at = from_address.rfind("@")
    if at < 0:
        return ""
    rest = from_address[at + 1 :].strip().rstrip(">").strip().lower()
    end = 0
    while end < len(rest) and (rest[end].isalnum() or rest[end] in ".-"):
        end += 1
    return rest[:end]


def display_sender(from_address: str) -> str:
    """Prefer the RFC display name, else a known-brand label, else the domain."""
    lt = from_address.find("<")
    if lt > 0:
        name = from_address[:lt].strip().strip('"').strip("'")
        if name:
            return name[:80]
    domain = email_domain(from_address)
    kind = _match_kind(domain)
    if kind is not None:
        return kind.label
    return domain[:80] if domain else from_address.strip()[:80]


def _domain_matches(domain: str, suffix: str) -> bool:
    return domain == suffix or domain.endswith("." + suffix)


def _match_kind(domain: str) -> _SenderKind | None:
    if not domain:
        return None
    for kind in _SENDERS:
        if any(_domain_matches(domain, suffix) for suffix in kind.domains):
            return kind
    return None


def _haystack(message: GmailMessage) -> str:
    return f"{message.subject} {message.snippet} {message.body_text[:400]}".lower()


def _clean_subject(subject: str) -> str:
    text = subject.strip()
    lowered = text.lower()
    for prefix in ("re:", "fwd:", "fw:"):
        if lowered.startswith(prefix):
            text = text[len(prefix) :].strip()
            lowered = text.lower()
            break
    return text[:200]


def _title_for(kind: _SenderKind, subject: str) -> str:
    cleaned = _clean_subject(subject)
    if kind.kind == "package":
        prefix = f"{kind.label} delivery"
    elif kind.kind == "reservation":
        prefix = f"{kind.label} reservation"
    else:
        prefix = f"{kind.label} appointment"
    if cleaned and cleaned.lower() not in {kind.label.lower(), prefix.lower()}:
        return f"{prefix} — {cleaned}"[:500]
    return prefix


def extract_from_sender_template(message: GmailMessage) -> SuggestedReminderItem | None:
    """Return a reminder when From + subject/snippet match a known sender cue."""
    from app.services.email import SuggestedReminderItem

    kind = _match_kind(email_domain(message.from_address))
    if kind is None:
        return None
    if not any(cue in _haystack(message) for cue in kind.cues):
        return None
    return SuggestedReminderItem(
        title=_title_for(kind, message.subject),
        due_at=None,
        notes=(message.snippet or None),
        confidence=0.85,
    )
