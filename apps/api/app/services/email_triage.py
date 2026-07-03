"""Heuristic inbox triage — surface mail that needs attention, hide noise."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from app.gateways.google_gmail_gateway import GmailMessage

NOISE_LABELS = frozenset(
    {"SPAM", "TRASH", "CATEGORY_PROMOTIONS", "CATEGORY_FORUMS", "CATEGORY_SOCIAL"}
)
AUTOMATED_FROM = re.compile(
    r"(^|[\s<])(?:no[-_.]?reply|donotreply|notifications?|newsletter|marketing|"
    r"mailer-daemon|bounce|updates?)(@|[\s>])",
    re.IGNORECASE,
)
PROMO_SUBJECT = re.compile(
    r"\b("
    r"unsubscribe|newsletter|"
    r"\d+\s*%\s*off|lowest price|legal agreement|"
    r"receipt|statement|view in browser|act now|limited time|"
    r"donate|mileageplus|support .+ with miles|"
    r"changes to our (?:paypal|terms|policy)|"
    r"lowered your .+ balance|balance this year"
    r")\b",
    re.IGNORECASE,
)
REPLY_LIKELY = re.compile(
    r"(\?|\b(request|invitation|invite|rsvp|confirm|action required|"
    r"please respond|follow up|following up|waiting for|can you)\b)",
    re.IGNORECASE,
)


class InboxBucket(StrEnum):
    NEEDS_ATTENTION = "needs_attention"
    FYI = "fyi"
    NOISE = "noise"


@dataclass(frozen=True)
class ClassifiedMessage:
    message: GmailMessage
    bucket: InboxBucket
    reason: str


def _short_from(from_address: str) -> str:
    clean = from_address.strip()
    if not clean:
        return "unknown sender"
    match = re.search(r"<([^>]+)>", clean)
    if match:
        return match.group(1).strip()
    return clean[:80]


def classify_message(message: GmailMessage) -> ClassifiedMessage:
    labels = set(message.label_ids)
    subject = message.subject or ""
    snippet = message.snippet or ""
    from_addr = message.from_address or ""

    if labels & {"SPAM", "TRASH"}:
        return ClassifiedMessage(message, InboxBucket.NOISE, "spam or trash")

    if "CATEGORY_PROMOTIONS" in labels:
        return ClassifiedMessage(message, InboxBucket.NOISE, "Gmail promotions")

    if PROMO_SUBJECT.search(subject) or PROMO_SUBJECT.search(snippet):
        return ClassifiedMessage(message, InboxBucket.NOISE, "promotional content")

    if AUTOMATED_FROM.search(from_addr) or AUTOMATED_FROM.search(subject):
        if REPLY_LIKELY.search(subject) or REPLY_LIKELY.search(snippet):
            return ClassifiedMessage(message, InboxBucket.FYI, "automated but may need a look")
        return ClassifiedMessage(message, InboxBucket.NOISE, "automated sender")

    if "IMPORTANT" in labels and "UNREAD" in labels:
        return ClassifiedMessage(
            message, InboxBucket.NEEDS_ATTENTION, "unread and marked important"
        )

    if REPLY_LIKELY.search(subject) or REPLY_LIKELY.search(snippet):
        return ClassifiedMessage(message, InboxBucket.NEEDS_ATTENTION, "likely expects a reply")

    if "UNREAD" in labels and not (labels & NOISE_LABELS):
        return ClassifiedMessage(message, InboxBucket.NEEDS_ATTENTION, "unread personal mail")

    if "CATEGORY_UPDATES" in labels or "CATEGORY_SOCIAL" in labels:
        return ClassifiedMessage(message, InboxBucket.FYI, "update or social notification")

    return ClassifiedMessage(message, InboxBucket.FYI, "informational")


def triage_messages(messages: list[GmailMessage]) -> list[ClassifiedMessage]:
    return [classify_message(message) for message in messages]


def format_triaged_inbox_block(
    *,
    google_email: str,
    messages: list[GmailMessage],
    pending_suggestions: list,
    fetch_error: str | None = None,
) -> str:
    """Structured inbox context for the model — not a user-facing dump."""
    lines = [f"Gmail triage (read-only, {google_email}):"]

    if fetch_error:
        lines.append(f"Inbox fetch failed: {fetch_error}")

    if pending_suggestions:
        lines.append(f"Pending suggested reminders ({len(pending_suggestions)}):")
        for row in pending_suggestions[:8]:
            due = f" — due {row.due_at.isoformat()}" if row.due_at else ""
            lines.append(f"- {row.title}{due}")

    if not messages and not pending_suggestions and not fetch_error:
        lines.append("No recent inbox messages found in the last sync window.")
        return "\n".join(lines)

    classified = triage_messages(messages)
    attention = [c for c in classified if c.bucket is InboxBucket.NEEDS_ATTENTION]
    fyi = [c for c in classified if c.bucket is InboxBucket.FYI]
    noise = [c for c in classified if c.bucket is InboxBucket.NOISE]

    lines.append("")
    if attention:
        lines.append(f"Needs attention ({len(attention)}):")
        for item in attention[:8]:
            msg = item.message
            snippet = (msg.snippet or "")[:140]
            lines.append(
                f"- Subject: {msg.subject or '(no subject)'} | "
                f"From: {_short_from(msg.from_address)} | "
                f"Why: {item.reason} | Snippet: {snippet}"
            )
    else:
        lines.append("Needs attention: none identified in recent mail.")

    if fyi:
        lines.append("")
        lines.append(f"FYI / low priority ({len(fyi)}):")
        for item in fyi[:4]:
            msg = item.message
            subj = msg.subject or "(no subject)"
            sender = _short_from(msg.from_address)
            lines.append(f"- {subj} ({sender}) — {item.reason}")

    if noise:
        lines.append("")
        lines.append(
            f"Filtered as promotional, automated, or spam ({len(noise)} messages — "
            "do not list these unless the user asks for everything."
        )

    return "\n".join(lines)
