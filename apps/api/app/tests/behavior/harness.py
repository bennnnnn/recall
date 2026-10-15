"""Route one battery prompt through the real turn path, offline, and say what happened.

The turn runs the way ``stream_entry`` runs it: the photo-lookup and image-generation
intercepts, the turn mode, the real prompt builder and pre-solvers, then the tool-loop
gate. Only IO is stubbed: the database, model health, the web and image
search providers, PubChem, and the model calls. The classifier and the tool rounds are
recorded instead of called, so the route says whether a model would have been asked.
"""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.core.config import Settings
from app.gateways.pubchem_gateway import PubChemCompound, PubChemResult
from app.gateways.web_search_gateway import WebSearchHit
from app.models.orm import Chat, User
from app.modules import web_search as web_search_service
from app.modules.chat import prompt_constants as pc
from app.modules.chat.prompt_context import _PromptContextBlocks
from app.modules.chat.turn_prep.context import (
    build_stream_prompt_context,
    stream_context_from_bundle,
)
from app.modules.chat.turn_prep.mode import _classify_turn_mode
from app.modules.images.gen_intent import extract_image_gen_prompt
from app.modules.images.lookup_intent import dated_lookup_query, extract_image_lookup_query
from app.modules.web_search.detection import needs_web_search
from app.services.subject_solving import detect_subject
from app.services.tool_loop import _search_before_the_model
from app.tests.behavior.cases import Case, Expect

EMOJI_RULE = "Do not decorate with emoji unless the user used them."

# Name → text that marks the hint in the system prompt.
HINTS: dict[str, str] = {
    "teaching": pc.TEACHING_HINT,
    "walkthrough": pc.WALKTHROUGH_HINT,
    "learning_plan": pc.LEARNING_PLAN_HINT,
    "comparison": pc.COMPARISON_FORMAT_HINT,
    "howto": pc.HOWTO_FORMAT_HINT,
    "steps": pc.STEPS_FORMAT_HINT,
    "chart": pc.CHART_FORMAT_HINT,
    "mermaid": pc.MERMAID_FORMAT_HINT,
    "email": pc.EMAIL_DRAFT_HINT,
    "ask_purpose": pc.EMAIL_ASK_PURPOSE_HINT,
    "social": pc.SOCIAL_DRAFT_HINT,
    "brevity": pc.BREVITY_REQUEST_HINT,
    "capabilities": pc.CAPABILITIES_FORMAT_HINT,
    "lightweight": pc.LIGHTWEIGHT_REPLY_HINT,
    "web_search": web_search_service.WEB_SEARCH_HINT,
    "photo": pc.PHOTO_LOOKUP_HINT,
    "local_places": web_search_service.LOCAL_PLACES_FORMAT_HINT,
    "answer_photo": pc.ANSWER_PHOTO_HINT,
    "where_is_photo": pc.WHERE_IS_PHOTO_HINT,
    "emoji_rule": EMOJI_RULE,
}

USER_NAME = "Bini"
USER_TIMEZONE = "Africa/Nairobi"


@dataclass
class Route:
    """What the turn did. Mirrors ``Expect``."""

    photo: str
    image_gen: bool
    search: str
    subject: str
    solved: bool
    instant: str
    lightweight: bool
    hints: set[str] = field(default_factory=set)
    # The ``programming_lesson`` contract is turn-specific text, not a constant.
    system_prompt: str = ""
    # What an instant (no-model) reply said, for the sweep to read.
    instant_text: str = ""
    # The verified result handed to the model when it writes the reply itself.
    verified_answer: str = ""
    verified_text: str = ""

    def summary(self) -> str:
        parts = [f"search={self.search}"]
        if self.photo:
            parts.append(f"photo={self.photo!r}")
        if self.image_gen:
            parts.append("image_gen")
        if self.subject:
            parts.append(f"subject={self.subject}{'+solved' if self.solved else ''}")
        if self.instant:
            parts.append(f"instant={self.instant}")
        if self.lightweight:
            parts.append("lightweight")
        if self.hints:
            parts.append("hints=" + ",".join(sorted(self.hints)))
        return " ".join(parts)


def battery_settings() -> Settings:
    """Every feature on, no provider keys: nothing leaves the process."""
    return Settings(  # type: ignore[call-arg]
        _env_file=None,
        mock_llm_enabled=True,
        openrouter_api_key="",
        openai_api_key="",
        tavily_api_key="",
        web_search_enabled=True,
        web_search_classifier_enabled=True,
        web_search_fallback_enabled=False,
        image_search_enabled=True,
        image_generation_enabled=True,
        math_tools_enabled=True,
        chemistry_enabled=True,
        mcp_tool_loop_enabled=True,
        attachments_enabled=False,
        attachment_rag_enabled=False,
        chat_history_rag_enabled=False,
        semantic_memory_enabled=False,
    )


class _Session:
    async def __aenter__(self) -> AsyncMock:
        return AsyncMock()

    async def __aexit__(self, *_args: object) -> None:
        return None


# The one compound a battery prompt names; every other lookup is "not found".
_PUBCHEM = {
    "caffeine": PubChemCompound(
        cid=2519,
        name="caffeine",
        smiles="CN1C=NC2=C1C(=O)N(C(=O)N2C)C",
        molecular_formula="C8H10N4O2",
        molecular_weight=194.19,
    ),
}


async def _pubchem_lookup(name: str, *_args: Any, **_kwargs: Any) -> PubChemResult:
    compound = _PUBCHEM.get(" ".join(name.split()).lower())
    return PubChemResult(compound=compound) if compound else PubChemResult(error="not found")


def _rows(case: Case) -> list[SimpleNamespace]:
    return [
        SimpleNamespace(id=uuid4(), role=role, content=text, model="free-chat")
        for role, text in case.history
    ]


def _instant_kind(reply: str | None, *, solved: bool) -> str:
    if not reply:
        return ""
    if reply.lstrip().startswith("```clock"):
        return "clock"
    if reply == web_search_service.format_location_not_set_answer():
        return "location"
    if solved:
        return "solver"
    return "text"


def _hints_in(system: str, case: Case) -> set[str]:
    found = {name for name, text in HINTS.items() if text and text in system}
    contract = pc.programming_lesson_contract(case.prompt)
    if contract and contract in system:
        found.add("programming_lesson")
    return found


async def route_case(case: Case, settings: Settings | None = None) -> Route:
    settings = settings or battery_settings()
    user = User(
        id=uuid4(),
        name=USER_NAME,
        email="bini@example.com",
        plan="pro" if case.pro else "free",
        response_style="balanced",
        response_tone="casual",
        locale="en",
        timezone=USER_TIMEZONE,
        memory_enabled=False,
        location=case.location,
        location_enabled=case.location is not None,
    )
    chat = Chat(id=uuid4(), user_id=user.id, title=None)
    rows = _rows(case)
    prior_users = [row.content for row in rows if row.role == "user"]
    last_assistant = next((row for row in reversed(rows) if row.role == "assistant"), None)
    text = case.prompt

    found = extract_image_lookup_query(text) if settings.image_search_enabled else None
    photo = dated_lookup_query(found, datetime.now(UTC).year) if found else ""
    image_gen = bool(
        not photo
        and settings.image_generation_enabled
        and case.pro
        and extract_image_gen_prompt(text)
    )

    searched: list[Any] = []

    async def run_search(*args: Any, **_kwargs: Any) -> tuple[list[WebSearchHit], list[str]]:
        searched.append(args)
        hit = WebSearchHit(title="Result", url="https://example.com", snippet="A result.")
        return [hit], [text]

    classifier = AsyncMock(return_value=None)
    tool_rounds = AsyncMock(side_effect=lambda **kw: (kw["messages"], None, None, []))

    async def context_blocks(*_args: Any, **_kwargs: Any) -> _PromptContextBlocks:
        return _PromptContextBlocks(
            memory_block="",
            todos_section=None,
            recent_all=list(rows),
            attachment_rag_block="",
            chat=chat,
        )

    with ExitStack() as stack:

        def stub(target: str, value: Any) -> None:
            stack.enter_context(patch(target, value))

        stub("app.modules.chat.turn_prep.context.SessionLocal", lambda: _Session())
        stub("app.modules.chat.prompt_builder._load_context_blocks", context_blocks)
        stub("app.repositories.messages.list_recent", AsyncMock(return_value=list(rows)))
        stub("app.repositories.messages.get_last_assistant", AsyncMock(return_value=last_assistant))
        stub("app.repositories.messages.recent_user_contents", AsyncMock(return_value=prior_users))
        stub("app.modules.memory.list_for_user", AsyncMock(return_value=[]))
        stub("app.services.model_health.enrich_models_health", AsyncMock(return_value={}))
        stub("app.modules.billing.plan.chat_fallback_models", lambda *_a, **_k: [])
        stub(
            "app.modules.chat.turn_prep.context._load_prior_user_messages",
            AsyncMock(return_value=prior_users),
        )
        stub("app.modules.web_search.search_cache.run_cached_search", run_search)
        stub("app.gateways.web_search_gateway.search_web", AsyncMock(return_value=[]))
        stub("app.gateways.pubchem_gateway.lookup_by_name", _pubchem_lookup)
        stub("app.gateways.pubchem_gateway.lookup_iupac_name", AsyncMock(return_value=None))
        stub("app.modules.web_search.detection.classify_web_search", classifier)
        stub("app.services.tool_loop.run_tool_rounds", tool_rounds)
        stub("app.services.quota.global_spend_exceeded", AsyncMock(return_value=False))

        turn_mode = await _classify_turn_mode(AsyncMock(), chat, text)
        bundle = await build_stream_prompt_context(
            user.id,
            chat.id,
            text,
            "free-chat",
            settings,
            AsyncMock(),
            client_timezone=USER_TIMEZONE,
            client_location=case.location,
            client_latitude=None,
            client_longitude=None,
            user=user,
            chat=chat,
            turn_mode=turn_mode,
            recent_messages=list(rows),
        )
        ctx = stream_context_from_bundle(
            bundle,
            user_id=user.id,
            chat_id=chat.id,
            model="free-chat",
            user_message_content=text,
            reserved_tokens=100,
            user=user,
            prior_count=len(rows),
        )
        prefetch_searched = bool(searched) or bool(bundle.search_sources)
        from app.modules.chat.stream import _run_tool_loop_path

        await _run_tool_loop_path(
            AsyncMock(), settings, ctx, usage={}, on_status=None, should_cancel=None
        )

    loop_call = tool_rounds.await_args
    loop_ran = loop_call is not None
    web_flag = loop_call.kwargs.get("web_search") if loop_call is not None else None
    direct = loop_ran and _search_before_the_model(text, settings, user, web_search=web_flag)
    if prefetch_searched or direct or (loop_ran and needs_web_search(text)):
        search = "yes"
    elif classifier.await_count or loop_ran:
        search = "ask"
    else:
        search = "no"

    subject = detect_subject(text, chemistry_enabled=settings.chemistry_enabled) or ""
    verified = bundle.verified_subject
    solved = verified is not None
    system = "\n\n".join(
        str(m.get("content")) for m in bundle.prompt_messages if m.get("role") == "system"
    )
    return Route(
        photo=photo,
        image_gen=image_gen,
        search=search,
        subject=subject,
        solved=solved,
        instant=_instant_kind(bundle.instant_reply, solved=solved),
        instant_text=bundle.instant_reply or "",
        lightweight=bool(bundle.lightweight),
        hints=_hints_in(system, case),
        system_prompt=system,
        verified_answer=(verified.display_answer or verified.canonical_answer or "")
        if verified
        else "",
        verified_text=verified.text if verified else "",
    )


def mismatches(expect: Expect, route: Route) -> list[str]:
    """Each way the route differs from what the case expects."""
    out: list[str] = []

    def check(name: str, want: object, got: object) -> None:
        if want is not None and want != got:
            out.append(f"{name}: expected {want!r}, got {got!r}")

    if expect.photo is not None:
        if expect.photo == "":
            check("photo", "", route.photo)
        elif expect.photo.lower() != route.photo.lower():
            out.append(f"photo: expected {expect.photo!r}, got {route.photo!r}")
    if expect.photo_not:
        words = route.photo.lower().split()
        if not route.photo:
            out.append("photo: expected a lookup, got none")
        for word in expect.photo_not:
            if word in words:
                out.append(f"photo: {route.photo!r} still says {word!r}")
    check("image_gen", expect.image_gen, route.image_gen)
    # An intercepted turn (photo or generated image) never reaches the rest.
    if route.photo or route.image_gen:
        return out
    check("search", expect.search, route.search)
    check("subject", expect.subject, route.subject)
    check("solved", expect.solved, route.solved)
    check("instant", expect.instant, route.instant)
    check("lightweight", expect.lightweight, route.lightweight)
    if expect.answer_photo and "answer_photo" not in route.hints:
        out.append("answer photo: the turn never offers one")
    for hint in expect.hints:
        if hint not in route.hints:
            out.append(f"hint {hint!r} missing")
    for hint in expect.no_hints:
        if hint in route.hints:
            out.append(f"hint {hint!r} present")
    return out
