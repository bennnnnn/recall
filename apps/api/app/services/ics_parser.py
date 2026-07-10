"""RFC 5545-ish ICS invite parsing for Gmail suggested reminders."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_PROP_RE = re.compile(r"^([^:;]+)(?:;([^:]*))?:(.*)$", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedIcsInvite:
    title: str | None
    due_at: datetime | None
    location: str | None = None
    description: str | None = None


def _unfold_ics(ics_content: str) -> str:
    normalized = ics_content.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    unfolded: list[str] = []
    for line in lines:
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    return "\n".join(unfolded)


def _unescape_ics_text(value: str) -> str:
    return (
        value.replace("\\n", " ")
        .replace("\\N", " ")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
        .strip()
    )


def _parse_property(line: str) -> tuple[str, dict[str, str], str] | None:
    match = _PROP_RE.match(line.strip())
    if not match:
        return None
    name = match.group(1).upper()
    param_str = match.group(2) or ""
    value = match.group(3)
    params: dict[str, str] = {}
    if param_str:
        for chunk in param_str.split(";"):
            if "=" not in chunk:
                continue
            key, raw = chunk.split("=", 1)
            params[key.strip().lower()] = raw.strip()
    return name, params, value


def _parse_ics_datetime(value: str, params: dict[str, str]) -> datetime | None:
    raw = value.strip()
    if not raw:
        return None

    tzid = params.get("tzid")
    is_date = params.get("value", "").upper() == "DATE" or ("T" not in raw and len(raw) == 8)

    try:
        if is_date:
            dt = datetime.strptime(raw[:8], "%Y%m%d")
            if tzid:
                return dt.replace(tzinfo=ZoneInfo(tzid))
            return dt.replace(tzinfo=UTC)

        if raw.endswith("Z"):
            return datetime.strptime(raw, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)

        if len(raw) >= 15:
            dt = datetime.strptime(raw[:15], "%Y%m%dT%H%M%S")
        elif len(raw) >= 13:
            dt = datetime.strptime(raw[:13], "%Y%m%dT%H%M")
        elif len(raw) >= 11:
            dt = datetime.strptime(raw[:11], "%Y%m%dT%H")
        else:
            return None

        if tzid:
            return dt.replace(tzinfo=ZoneInfo(tzid))
        return dt.replace(tzinfo=UTC)
    except (ValueError, ZoneInfoNotFoundError):
        return None


def _split_vevent_blocks(unfolded: str) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] | None = None
    for line in unfolded.split("\n"):
        upper = line.strip().upper()
        if upper == "BEGIN:VEVENT":
            current = []
        elif upper == "END:VEVENT" and current is not None:
            blocks.append(current)
            current = None
        elif current is not None and line.strip():
            current.append(line)
    return blocks


def _parse_vevent(lines: list[str]) -> ParsedIcsInvite | None:
    summary: str | None = None
    due_at: datetime | None = None
    location: str | None = None
    description: str | None = None
    status: str | None = None

    for line in lines:
        parsed = _parse_property(line)
        if parsed is None:
            continue
        name, params, value = parsed
        if name == "STATUS":
            status = value.strip().upper()
        elif name == "SUMMARY" and summary is None:
            summary = _unescape_ics_text(value) or None
        elif name == "DTSTART" and due_at is None:
            due_at = _parse_ics_datetime(value, params)
        elif name == "LOCATION" and location is None:
            location = _unescape_ics_text(value) or None
        elif name == "DESCRIPTION" and description is None:
            description = _unescape_ics_text(value) or None

    if status == "CANCELLED":
        return None
    if not summary and due_at is None:
        return None
    return ParsedIcsInvite(
        title=summary,
        due_at=due_at,
        location=location,
        description=description,
    )


def parse_ics_invite(ics_content: str) -> ParsedIcsInvite | None:
    """Parse the first actionable VEVENT from calendar invite text."""
    if not ics_content.strip():
        return None
    unfolded = _unfold_ics(ics_content)
    blocks = _split_vevent_blocks(unfolded)
    if blocks:
        for block in blocks:
            invite = _parse_vevent(block)
            if invite is not None:
                return invite
        return None
    # Gmail snippets sometimes omit VCALENDAR/VEVENT wrappers.
    loose_lines = [line for line in unfolded.split("\n") if line.strip()]
    if not loose_lines:
        return None
    return _parse_vevent(loose_lines)


def parse_ics_event(ics_content: str) -> tuple[str | None, datetime | None]:
    """Backward-compatible title + start time tuple."""
    invite = parse_ics_invite(ics_content)
    if invite is None:
        return None, None
    return invite.title, invite.due_at
