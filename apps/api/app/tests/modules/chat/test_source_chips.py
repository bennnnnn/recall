"""A searched reply's source chips are the pages it used, not every page the search found.

On the owner's phone (2026-11-09) "Can i wolk?" showed a Kentucky charity PDF and an Idaho
emigrant-trails paper, and "Where is the nearest one" a UPS Store and an Apple jobs page:
every hit was a chip. The claim check's model call now names the pages the reply used. The
model is stubbed here; what is held is what the passes do with its answer.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.gateways.web_search_gateway import WebSearchHit
from app.modules import web_search as web_search_service
from app.modules.chat import claim_check
from app.modules.chat.claim_check import cut_unsupported_claims
from app.modules.chat.claim_sources import SOURCES_USED_RULE, pages_used
from app.modules.chat.finalize_passes import FinalizeState
from app.modules.chat.finalize_text import add_search_sources
from app.modules.chat.turn_outcome import TurnOutcome
from app.modules.chat.turn_prep import StreamContext
from app.services.md_fence_scan import iter_closed_fences
from app.tests.modules.chat.chat_test_support import turn_deps

_STORE = WebSearchHit(
    title="Apple Bellevue Square - Apple Store",
    url="https://www.apple.com/retail/bellevuesquare",
    snippet="Apple Bellevue Square, 213 Bellevue Square, Bellevue, WA 98004. Genius Bar by appointment.",
)
_UPS = WebSearchHit(
    title="The UPS Store Bellevue WA",
    url="https://locations.theupsstore.com/wa/bellevue/10900-ne-8th-st",
    snippet="Packing, shipping, printing and mailbox services at 10900 NE 8th St.",
)
_JOBS = WebSearchHit(
    title="Retail jobs at Apple",
    url="https://www.apple.com/careers/us/retail.html",
    snippet="Specialist and Genius roles at Apple Store locations, including Bellevue, WA.",
)
_NEAREST = (
    "The nearest Apple Store is **Apple Bellevue Square**, 213 Bellevue Square, Bellevue, "
    "WA 98004. The Genius Bar works by appointment, so book one before you go."
)
_CHARITY = WebSearchHit(
    title="2025 Walk for Kids Registration Packet",
    url="https://kychildrenscharity.org/walk-registration.pdf",
    snippet="Can I walk with my dog? Yes, leashed pets are welcome on the 5K route in Louisville.",
)
_TRAILS = WebSearchHit(
    title="Emigrant Trails of Southern Idaho",
    url="https://www.blm.gov/idaho-emigrant-trails.pdf",
    snippet="Travelers walked beside their wagons, covering 15 to 20 miles a day.",
)
_WALK = "Yes, if you're downtown: the store is about a 10-minute walk."


def _state(reply: str, pages: list[WebSearchHit], message: str) -> FinalizeState:
    ctx = StreamContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        model="gpt-6-luna",
        prompt_messages=[{"role": "user", "content": message}],
        run_title=False,
        user_message_content=message,
        reserved_tokens=0,
        max_output_tokens=0,
        search_sources=list(pages),
    )
    return FinalizeState(
        deps=turn_deps(web_search=web_search_service),
        settings=Settings(),
        ctx=ctx,
        raw=reply,
        text=reply,
        usage={},
        outcome=TurnOutcome(),
        was_cancelled=False,
        should_cancel=None,
    )


async def _finalize(state: FinalizeState, verdict: Any) -> str:
    """The claim check, then the chips, as ``FINALIZE_PASSES`` orders them."""
    ask = AsyncMock(return_value=verdict)
    with patch.object(claim_check, "complete_structured", ask):
        state.text = await cut_unsupported_claims(state)
    return add_search_sources(state)


def _chip_urls(text: str) -> list[str]:
    bodies = [body for _start, _end, body in iter_closed_fences(text, "sources")]
    return [row["url"] for body in bodies for row in json.loads(body)]


def _verdict(**fields: Any) -> claim_check._Verdict:
    return claim_check._Verdict.model_validate(fields)


async def test_only_the_page_the_reply_used_is_a_chip() -> None:
    state = _state(_NEAREST, [_STORE, _UPS, _JOBS], "Where is the nearest one")
    out = await _finalize(state, _verdict(used=[1]))
    assert out.startswith(_NEAREST)
    assert _chip_urls(out) == [_STORE.url]
    assert state.outcome is not None
    assert [row["url"] for row in state.outcome.search_sources] == [_STORE.url]


async def test_a_short_reply_that_used_no_page_shows_no_chips() -> None:
    """The reply came from the chat, not the pages; it is short, so nothing is cut."""
    state = _state(_WALK, [_CHARITY, _TRAILS], "Can i wolk?")
    flagged = {"unsupported": [{"quote": "about a 10-minute walk", "kind": "figure"}]}
    out = await _finalize(state, _verdict(used=[], **flagged))
    assert out == _WALK
    assert state.outcome is not None
    assert state.outcome.search_sources == []


async def test_a_short_reply_is_read_for_its_pages() -> None:
    state = _state("Bitcoin is at $74,586 on Yahoo Finance.", [_UPS, _STORE], "btc?")
    ask = AsyncMock(return_value=_verdict(used=[2]))
    with patch.object(claim_check, "complete_structured", ask):
        await cut_unsupported_claims(state)
    ask.assert_awaited_once()
    assert state.sources_used == [1]


@pytest.mark.parametrize(
    "verdict",
    [None, claim_check._Verdict(), claim_check._Verdict.model_validate({"used": ["Xe"]})],
    ids=["check failed", "used not given", "used not readable"],
)
async def test_a_check_that_says_nothing_of_the_pages_keeps_every_chip(verdict: Any) -> None:
    state = _state(_NEAREST, [_STORE, _UPS, _JOBS], "Where is the nearest one")
    out = await _finalize(state, verdict)
    assert _chip_urls(out) == [_STORE.url, _UPS.url, _JOBS.url]


async def test_a_turn_the_check_skips_keeps_every_chip() -> None:
    state = _state(_NEAREST, [_STORE, _UPS], "Where is the nearest one")
    state.settings = Settings(claim_check_enabled=False)
    out = await _finalize(state, _verdict(used=[1]))
    assert _chip_urls(out) == [_STORE.url, _UPS.url]


def test_page_numbers_are_read_however_the_checker_wrote_them() -> None:
    """A page written as {"id": 1, "claims": [...]} failed the whole verdict, cuts and all."""
    written = [{"id": 2, "claims": ["the date"]}, "3", "[4]", True, None]
    assert _verdict(used=written).used == [2, 3, 4]
    assert _verdict(used=[]).used == []
    assert _verdict(used=[{"title": "Xe"}]).used is None
    assert _verdict(used="1, 2").used is None


def test_numbers_outside_the_pages_name_none_of_them() -> None:
    # Numbered from 1; a number past what it read, or below 1, names no page.
    assert pages_used([3, 1, 1, 9, 0, -2], seen=8, total=8) == [0, 2]
    assert pages_used(None, seen=8, total=8) is None
    assert pages_used([], seen=8, total=8) == []


@pytest.mark.parametrize("used", [[0], [9], [0, 9, -1]])
def test_a_list_of_only_numbers_outside_the_pages_keeps_every_chip(used: list[int]) -> None:
    assert pages_used(used, seen=8, total=8) is None


def test_pages_the_checker_never_saw_keep_their_chips() -> None:
    """Hits from several searches merge without a cap; the checker reads the first 8."""
    assert pages_used([2], seen=8, total=10) == [1, 8, 9]
    assert pages_used([], seen=8, total=10) == [8, 9]


async def test_a_ninth_page_stays_a_chip_after_the_check() -> None:
    pages = [_UPS] * 8 + [_STORE]
    state = _state(_NEAREST, pages, "Where is the nearest one")
    out = await _finalize(state, _verdict(used=[1]))
    assert _chip_urls(out) == [_UPS.url, _STORE.url]


def test_a_number_written_as_a_superscript_never_fails_the_verdict() -> None:
    """ "²" passes isdigit but not int(): the whole verdict, its cuts too, was lost."""
    verdict = _verdict(used=["²", "3"], unsupported=[{"quote": "Cytonn is reinstated"}])
    assert verdict.used == [3]
    assert len(verdict.unsupported) == 1


async def test_a_short_reply_waits_only_briefly_for_its_pages() -> None:
    state = _state(_WALK, [_CHARITY, _TRAILS], "Can i wolk?")
    state.settings = Settings(claim_check_short_timeout_seconds=1.5)
    ask = AsyncMock(return_value=None)
    with patch.object(claim_check, "complete_structured", ask):
        out = await cut_unsupported_claims(state)
    assert out == _WALK
    assert ask.await_args is not None
    assert ask.await_args.kwargs["timeout_seconds"] == 1.5
    assert state.sources_used is None  # past it, every chip stays


async def test_a_long_reply_keeps_the_checks_own_deadline() -> None:
    state = _state(_NEAREST, [_STORE, _UPS], "Where is the nearest one")
    ask = AsyncMock(return_value=None)
    with patch.object(claim_check, "complete_structured", ask):
        await cut_unsupported_claims(state)
    assert ask.await_args is not None
    assert ask.await_args.kwargs["timeout_seconds"] == Settings().claim_check_timeout_seconds


def test_the_checker_is_asked_which_pages_the_reply_used() -> None:
    assert '"used": [...]' in claim_check._SYSTEM
    assert SOURCES_USED_RULE in claim_check._SYSTEM
