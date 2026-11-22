"""Measure "can u show me a picture" after a homework answer: drawn, said in words, or bad.

A script, not a test: it calls the real models through the gateway (the turn's read, the
referent and figure reads, the reply's model, a judge) and PubChem, so it needs an
OpenRouter key in the environment and nothing else (no database).

    python -m app.tests.behavior.picture_followup_eval
    python -m app.tests.behavior.picture_followup_eval --only physics --show

Every turn of ``picture_followup_corpus.json`` is a homework question and the reply the app
gave it (a QA round of simulated students, 2026-11-22), then a follow-up. Labelled ``draw``,
the follow-up asks to see a picture: of 45 only 6 drew anything; the rest got "I couldn't draw
this molecule.", "What would you like to see?", "I can't generate images", an empty reply or a
puppy nobody drew. Labelled ``none``, it asks for no picture (the steps again, a thanks): a
look-alike, which no picture, photo or painting answers.

Each turn runs as the chat turn runs it, with only the database, the web search and the
tool rounds stubbed: the read starts with the turn, the intercept decides a photo or a
painting (recorded, not made), the prep and its solves, the read's decisions, the reply
streamed by its model, and every finalize pass (the figure, the owed picture). A judge then
calls each ``draw`` reply one of:

- ``drew``: a picture of what the homework is about, drawn by the app;
- ``words``: no picture, and the reply says honestly what it can show or describes it;
- ``bad``: a wrong picture, a bare "I couldn't draw this X.", a question back about what to
  show, a claim of a picture that is not there, a refusal, a photo or painting, or nothing.

A ``none`` turn is ``ok`` with no picture, photo or painting, else ``picture``.

Measured 2026-11-22 (free plan, one run each): the 45 QA requests went from 3 drawn, 3 said
in words and 39 bad to 21 drawn, 20 in words and 4 bad; six other wordings ("pic pls", "draw
it for me", "what does it look like") from 2 drawn and 4 bad to 4 drawn and 2 in words; the
16 look-alikes kept 13 to 14 with no picture either way (a teaching structure on a
chemistry follow-up comes and goes run to run).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from collections import Counter
from contextlib import ExitStack
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx

CORPUS = Path(__file__).with_name("picture_followup_corpus.json")
_CONCURRENCY = 4
_JUDGE = "anthropic/claude-haiku-5.5"
_PICTURES = frozenset(
    {"graph", "geometry", "simulation", "chart", "smiles", "molecule3d", "chemistry", "vega"}
)
_FENCE = re.compile(r"```(\w[\w-]*)\n(.*?)```", re.DOTALL)
_VERDICT = re.compile(r'"verdict"\s*:\s*"(drew|words|bad)"')
_WHY = re.compile(r'"why"\s*:\s*"([^"]*)')

_RUBRIC = (
    "A student asked a homework question, got an answer, then asked to see a picture. You "
    "see the question, the answer, and the app's reply to the request. A fenced block "
    "summarised as [picture: kind ...] is a picture the app drew and showed. Call the reply:\n"
    '- "drew": it shows a picture (a graph, a diagram or scene, a molecule) of what the '
    "homework is about, matching its values\n"
    '- "words": it shows no picture, but honestly says in words what such a picture would '
    "show, or what it can show instead, without claiming a picture is there\n"
    '- "bad": anything else: a picture of something else, a bare "I couldn\'t draw this", '
    "asking what they would like to see, claiming a picture that is not shown, saying it "
    "cannot make images, a photo or an AI painting, or an empty reply\n"
    'Reply with JSON only: {"verdict": "drew" | "words" | "bad", "why": "<12 words>"}'
)


@dataclass
class _Turn:
    """One turn's chat, as the stubbed database gives it; what the intercept made."""

    rows: list[Any]
    saved: list[Any]
    chat: Any
    made: list[str] = field(default_factory=list)


# Each turn's own, read by the stubs patched once for every turn: patched per turn, turns run
# side by side read one another's chats.
_TURN: ContextVar[_Turn] = ContextVar("picture_followup_turn")


async def _made_photo(*_args: Any, **_kwargs: Any) -> bool:
    _TURN.get().made.append("photo")
    return True


async def _made_painting(*_args: Any, **_kwargs: Any) -> bool:
    _TURN.get().made.append("painting")
    return True


async def _context_blocks(*_args: Any, **_kwargs: Any) -> Any:
    from app.modules.chat.prompt_context import _PromptContextBlocks

    turn = _TURN.get()
    return _PromptContextBlocks(
        memory_block="",
        todos_section=None,
        recent_all=list(turn.saved),
        attachment_rag_block="",
        chat=turn.chat,
    )


async def _list_recent(*_args: Any, **_kwargs: Any) -> list[Any]:
    return list(_TURN.get().rows)


def _stubbed(settings: Any) -> ExitStack:
    """The database, model health, the web and the tool rounds, stubbed for every turn."""
    from app.tests.behavior.harness import _production_tools, _Session

    stack = ExitStack()
    for target, value in (
        ("app.modules.chat.turn_intercepts.try_image_lookup_for_turn", _made_photo),
        ("app.modules.chat.turn_intercepts.try_image_gen_for_turn", _made_painting),
        ("app.modules.chat.turn_prep.instant.SessionLocal", lambda: _Session()),
        ("app.modules.chat.prompt_builder._load_context_blocks", _context_blocks),
        ("app.modules.chat.practice_asked._chat_replies", AsyncMock(return_value=[])),
        ("app.modules.conversation.messages_repository.list_recent", _list_recent),
        ("app.modules.memory.repository.list_for_user", AsyncMock(return_value=[])),
        ("app.services.model_health.enrich_models_health", AsyncMock(return_value={})),
        ("app.modules.billing.plan.chat_fallback_models", lambda *_a, **_k: []),
        ("app.gateways.web_search_gateway.search_web", AsyncMock(return_value=[])),
        (
            "app.modules.chat.tool_loop.run_tool_rounds",
            AsyncMock(side_effect=lambda **kw: (kw["messages"], None, None, [])),
        ),
    ):
        stack.enter_context(patch(target, value))
    stack.enter_context(_production_tools(settings))
    return stack


def load(path: Path = CORPUS) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    return rows


def pictures_in(text: str) -> list[str]:
    """The app's pictures a reply shows, by fence language."""
    return [m.group(1) for m in _FENCE.finditer(text) if m.group(1) in _PICTURES]


def shown_to_judge(text: str) -> str:
    """The reply with each picture's fence summarised: its kind and the start of its spec."""

    def summary(match: re.Match[str]) -> str:
        lang, body = match.group(1), " ".join(match.group(2).split())
        if lang not in _PICTURES:
            return match.group(0)
        return f"[picture: {lang} {body[:300]}]"

    return _FENCE.sub(summary, text)


async def run_turn(settings: Any, row: dict[str, Any]) -> tuple[str, str]:
    """The turn's saved reply, and what the intercept did instead ("photo", "painting")."""
    from app.core import readings
    from app.models.orm import Chat, User
    from app.modules.chat import turn_intercepts
    from app.modules.chat.decided_turn import decide_from_the_read
    from app.modules.chat.figure_turn import LIVE_READ
    from app.modules.chat.finalize_passes import enrich_final_content
    from app.modules.chat.model_routing import choice as model_choice
    from app.modules.chat.model_routing.route import last_user_turn
    from app.modules.chat.stream_entry import _attach_reads
    from app.modules.chat.stream_paths import run_tool_loop_path
    from app.modules.chat.turn_decision import start_turn_decision
    from app.modules.chat.turn_deps import default_deps
    from app.modules.chat.turn_outcome import TurnOutcome
    from app.modules.chat.turn_prep.context import (
        build_stream_prompt_context,
        stream_context_from_bundle,
    )
    from app.modules.chat.turn_prep.mode import classify_turn_mode
    from app.modules.chat.turn_prep.reading import read_turn_message
    from app.modules.chat.turn_prep.request import TurnRequest
    from app.tests.behavior.harness import USER_TIMEZONE, _no_reminders, _no_session

    readings.begin_turn()
    user = User(
        id=uuid4(),
        name="Sam",
        email="sam@example.com",
        plan="free",
        response_tone="casual",
        emoji_use="some",
        locale="en",
        timezone=USER_TIMEZONE,
        memory_enabled=False,
    )
    chat = Chat(id=uuid4(), user_id=user.id, title=None)
    rows = [
        SimpleNamespace(id=uuid4(), role=role, content=text, model="free-chat")
        for role, text in row["history"]
    ]
    text = row["prompt"]
    await read_turn_message(text, rows, settings)
    prior_user, prior_model = last_user_turn(rows)
    model = model_choice.resolve_user_model(
        user, text, settings, prior_user=prior_user, prior_model=prior_model
    )
    read = start_turn_decision(settings, text, recent=rows)
    readings.keep_for_turn(LIVE_READ, read)
    turn = _Turn(
        rows=rows,
        # The window the prompt reads, as the database gives it once the user's row is saved.
        saved=[*rows, SimpleNamespace(id=uuid4(), role="user", content=text, model=None)],
        chat=chat,
    )
    _TURN.set(turn)
    deps = default_deps()
    misses: set[str] = set()
    if await turn_intercepts.intercept_new_turn(
        deps,
        settings,
        user=user,
        chat_id=chat.id,
        content=text,
        outcome=None,
        recent_messages=rows,
        prior_count=len(rows),
        misses=misses,
        read=read,
    ):
        return "", turn.made[0] if turn.made else "intercepted"
    bundle = await build_stream_prompt_context(
        TurnRequest(
            user_id=user.id,
            chat_id=chat.id,
            content=text,
            model=model,
            client_timezone=USER_TIMEZONE,
            client_location=None,
            client_latitude=None,
            client_longitude=None,
            user=user,
            chat=chat,
            turn_mode=classify_turn_mode(list(rows), text),
            recent_messages=list(rows),
        ),
        settings,
        AsyncMock(),
    )
    ctx = stream_context_from_bundle(
        bundle,
        user_id=user.id,
        chat_id=chat.id,
        model=model,
        user_message_content=text,
        reserved_tokens=100,
        user=user,
        prior_count=len(rows),
    )
    _attach_reads(ctx, settings, read, misses)
    reply = ctx.instant_reply or ""
    if not reply:
        await run_tool_loop_path(
            deps, AsyncMock(), settings, ctx, usage={}, on_status=None, should_cancel=None
        )
        reply = ctx.instant_reply or ""
    if not reply:
        await decide_from_the_read(ctx, settings)
        parts = [
            token
            async for token in deps.llm.stream_chat_completion(
                settings=settings,
                model_alias=ctx.model,
                messages=ctx.prompt_messages,
                max_tokens=ctx.max_output_tokens,
                thinking=ctx.thinking,
            )
        ]
        reply = "".join(parts)
    saving = SimpleNamespace(
        session_factory=_no_session,
        users=SimpleNamespace(get_by_id=AsyncMock(return_value=None)),
        todos=SimpleNamespace(materialize_reminder_fences=AsyncMock(side_effect=_no_reminders)),
    )
    saved = await enrich_final_content(
        replace(deps, **vars(saving)),
        AsyncMock(),
        settings,
        ctx,
        assistant_text=reply,
        usage={},
        outcome=TurnOutcome(),
        was_cancelled=False,
        should_cancel=None,
    )
    return saved, ""


async def judge(client: httpx.AsyncClient, row: dict[str, Any], reply: str) -> dict[str, str]:
    question, answer = row["history"][0][1], row["history"][1][1]
    content = (
        f"Question: {question[:800]}\n\nAnswer: {shown_to_judge(answer)[:1500]}\n\n"
        f"Request: {row['prompt']}\n\nReply: {shown_to_judge(reply)[:2000] or '(empty)'}"
    )
    for _attempt in range(3):
        try:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                json={
                    "model": _JUDGE,
                    "messages": [
                        {"role": "system", "content": _RUBRIC},
                        {"role": "user", "content": content},
                    ],
                    # The judge thinks first: a short budget cut its answer off.
                    "max_tokens": 2000,
                    "temperature": 0,
                },
            )
            said = response.json()["choices"][0]["message"].get("content") or ""
        except (httpx.HTTPError, KeyError, ValueError):
            await asyncio.sleep(2)
            continue
        verdict = _VERDICT.search(said)
        if verdict is not None:
            why = _WHY.search(said)
            return {"verdict": verdict.group(1), "why": why.group(1) if why else ""}
    return {"verdict": "bad", "why": "no verdict"}


async def measure(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from app.core.config import Settings
    from app.tests.fakes import redis_mock

    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        mock_llm_enabled=False,
        openrouter_api_key=os.environ["OPENROUTER_API_KEY"],
        tavily_api_key="",
        image_search_enabled=True,
        image_generation_enabled=True,
        chemistry_enabled=True,
        attachments_enabled=False,
        chat_history_rag_enabled=False,
        semantic_memory_enabled=False,
        # A cold pool's first readings are no declined turn here, as in the battery.
        stem_solve_timeout_seconds=30.0,
        subject_read_timeout_seconds=30.0,
    )
    from app.core.sympy_executor import warm_sympy_pool
    from app.modules.math.sympy_warmup import warm_math_worker

    await warm_sympy_pool(warm_math_worker)
    gate = asyncio.Semaphore(_CONCURRENCY)
    headers = {"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"}
    results: list[dict[str, Any]] = []

    async def never_capped(*_args: Any, **_kwargs: Any) -> bool:
        return False

    async with httpx.AsyncClient(timeout=60, headers=headers) as client:

        async def one(row: dict[str, Any]) -> None:
            async with gate:
                try:
                    reply, made = await run_turn(settings, row)
                except Exception as exc:  # A turn that fails is reported, never the run.
                    reply, made = f"(turn failed: {type(exc).__name__}: {exc})", "failed"
                shown = pictures_in(reply)
                if row["label"] == "none":
                    verdict = {"verdict": "picture" if shown or made else "ok", "why": ""}
                elif made:
                    verdict = {"verdict": "bad", "why": f"a {made} in its place"}
                else:
                    verdict = await judge(client, row, reply)
                results.append({**row, "reply": reply, "made": made, "shown": shown, **verdict})

        redis = redis_mock(get=None)
        with (
            patch("app.services.quota.global_spend_exceeded", never_capped),
            patch("app.core.redis.get_redis_client", lambda: redis),
            _stubbed(settings),
        ):
            await asyncio.gather(*(one(row) for row in rows))
    return sorted(results, key=lambda r: r["id"])


async def rejudge(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The replies a run saved, judged again (the judge's rubric or budget changed)."""
    headers = {"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"}
    gate = asyncio.Semaphore(_CONCURRENCY)
    async with httpx.AsyncClient(timeout=60, headers=headers) as client:

        async def one(row: dict[str, Any]) -> None:
            if row["label"] != "draw" or row["made"]:
                return
            async with gate:
                row.update(await judge(client, row, row["reply"]))

        await asyncio.gather(*(one(row) for row in results))
    return results


def report(results: list[dict[str, Any]], *, show: bool = False) -> str:
    lines: list[str] = []
    for label in ("draw", "none"):
        rows = [r for r in results if r["label"] == label]
        if not rows:
            continue
        counts = Counter(r["verdict"] for r in rows)
        by_subject = Counter((r["subject"], r["verdict"]) for r in rows)
        lines.append(
            f"{label}: {len(rows)} turns  " + "  ".join(f"{k} {v}" for k, v in counts.most_common())
        )
        for subject in sorted({r["subject"] for r in rows}):
            got = "  ".join(f"{v} {n}" for (s, v), n in sorted(by_subject.items()) if s == subject)
            lines.append(f"  {subject:<10} {got}")
    for r in results:
        if show or r["verdict"] in {"bad", "picture"}:
            reply = " ".join(shown_to_judge(r["reply"]).split())[:220]
            lines.append(
                f"- {r['id']:<22} {r['verdict']:<7} {r['prompt']!r}: {reply} ({r.get('why', '')})"
            )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="one subject, or rows whose id holds this")
    parser.add_argument("--label", choices=("draw", "none"))
    parser.add_argument("--show", action="store_true", help="every reply, not only the misses")
    parser.add_argument("--out", help="write the results as JSON here")
    parser.add_argument("--rejudge", help="judge the replies a run wrote with --out again")
    args = parser.parse_args()
    rows = [
        r
        for r in load()
        if (not args.only or args.only == r["subject"] or args.only in r["id"])
        and (not args.label or r["label"] == args.label)
    ]
    results = asyncio.run(
        rejudge(json.loads(Path(args.rejudge).read_text(encoding="utf-8")))
        if args.rejudge
        else measure(rows)
    )
    if args.out:
        Path(args.out).write_text(json.dumps(results, indent=1, ensure_ascii=False))
    print(report(results, show=args.show))


if __name__ == "__main__":
    main()
