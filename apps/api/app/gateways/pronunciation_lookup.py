"""Best-effort English pronunciation audio URLs (free Dictionary API)."""

from __future__ import annotations

import logging
import re

from app.gateways.http_client import get_pooled_client

logger = logging.getLogger(__name__)

_DICTIONARY_API = "https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
_WORD_RE = re.compile(r"^[a-z][a-z'-]{0,48}$")


async def lookup_pronunciation_url(word: str) -> str | None:
    """Return an HTTPS audio clip URL for a single English word, if available."""
    cleaned = word.strip().lower()
    if not _WORD_RE.match(cleaned):
        return None
    try:
        client = get_pooled_client(5.0)
        response = await client.get(_DICTIONARY_API.format(word=cleaned))
        if response.status_code != 200:
            return None
        data = response.json()
        if not isinstance(data, list):
            return None
        for entry in data:
            if not isinstance(entry, dict):
                continue
            phonetics = entry.get("phonetics")
            if not isinstance(phonetics, list):
                continue
            for phonetic in phonetics:
                if not isinstance(phonetic, dict):
                    continue
                audio = str(phonetic.get("audio") or "").strip()
                if audio.startswith("https://"):
                    return audio
    except Exception:
        logger.debug("Pronunciation lookup failed for %r", word, exc_info=True)
    return None
