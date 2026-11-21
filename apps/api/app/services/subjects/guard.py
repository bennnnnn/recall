"""One subject's bug costs that subject's answer, never another subject's turn.

Chat asks every registered subject about every line: whether it continues the subject's
last problem, which lane it suggests, whether its switch is on. An exception there crashed
the turn, so one broken subject failed every turn, "hi there" included: chemistry's
``continues_alone`` raising failed maths, physics and plain chat alike (audit REL-01,
2026-11-13). The registry hands chat each adapter inside ``GuardedSubject``: a member that
raises is logged (its traceback the first time) and answers as a subject with
nothing to say would: False, None, the text as it was, no solve. The subject order asks
the subjects' readers directly (``order``): a step whose reader raises switches its subject
off for the line, which is read again without it, so that subject never has the line and
every other still reads it.

The fence is not guarded. Its members run inside the finalize passes, which fail closed
on their own (a safety pass that raises gives way to its strip): a guard that kept the text
would let a model's forged card through. The proxies are plain classes at module level, so
the members the SymPy pool runs (``direct_reply``, ``shown_problem``, the tool's checks)
pickle as they did.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from contextlib import AbstractContextManager, nullcontext
from typing import TYPE_CHECKING, Any

from app.services.graph_facts import GraphFactReader
from app.services.solving import PhotoReading, SubjectAugmentation

if TYPE_CHECKING:
    from app.core.config import Settings
    from app.services.formal.answer import FormalAnswer
    from app.services.solving import SubjectName, VerifiedSolveBlock
    from app.services.subject_hints import SubjectHints
    from app.services.subjects.registry import (
        SubjectAdapter,
        SubjectFence,
        SubjectFigure,
        SubjectFollowups,
        SubjectFormal,
        SubjectPhoto,
        SubjectRequest,
        SubjectTool,
    )

logger = logging.getLogger(__name__)

# (subject, member) pairs that have failed: each is logged with its traceback once.
_FAILED: set[tuple[str, str]] = set()


def neutral_on_error[T](subject: str, member: str, neutral: T, call: Callable[[], T]) -> T:
    """``call()``, or ``neutral`` when it raises (its traceback logged once per member)."""
    try:
        return call()
    except Exception:
        if first_failure(subject, member):
            logger.exception("subject %s.%s failed; the turn goes on without it", subject, member)
        else:
            logger.info("subject %s.%s failed again", subject, member)
        return neutral


async def _neutral_async[T](
    subject: str, member: str, neutral: T, call: Callable[[], Awaitable[T]]
) -> T:
    try:
        return await call()
    except Exception:
        if first_failure(subject, member):
            logger.exception("subject %s.%s failed; the turn goes on without it", subject, member)
        else:
            logger.info("subject %s.%s failed again", subject, member)
        return neutral


def first_failure(subject: str, member: str) -> bool:
    """The first time ``subject``'s ``member`` failed: its traceback is logged then only."""
    if (subject, member) in _FAILED:
        return False
    _FAILED.add((subject, member))
    return True


class GuardedFollowups:
    """A subject's follow-up reading; a failing member reads the line as no follow-up."""

    def __init__(self, inner: SubjectFollowups, subject: str) -> None:
        self._inner = inner
        self._subject = subject

    def problem(
        self,
        query: str | None,
        recent: Sequence[Any],
        *,
        blocked: Callable[[str], bool] | None = None,
    ) -> str | None:
        return neutral_on_error(
            self._subject,
            "followups.problem",
            None,
            lambda: self._inner.problem(query, recent, blocked=blocked),
        )

    def continues(
        self,
        query: str | None,
        recent: Sequence[Any],
        *,
        blocked: Callable[[str], bool] | None = None,
    ) -> bool:
        return neutral_on_error(
            self._subject,
            "followups.continues",
            False,
            lambda: self._inner.continues(query, recent, blocked=blocked),
        )

    def previous_result(self, reply: str) -> str | None:
        return neutral_on_error(
            self._subject,
            "followups.previous_result",
            None,
            lambda: self._inner.previous_result(reply),
        )

    def continues_alone(self, line: str) -> bool:
        return neutral_on_error(
            self._subject,
            "followups.continues_alone",
            False,
            lambda: self._inner.continues_alone(line),
        )

    def borrows_earlier(self, line: str) -> bool:
        return neutral_on_error(
            self._subject,
            "followups.borrows_earlier",
            False,
            lambda: self._inner.borrows_earlier(line),
        )

    def asks_to_see(self, line: str, recent: Sequence[Any] | None = None) -> bool:
        return neutral_on_error(
            self._subject,
            "followups.asks_to_see",
            False,
            lambda: self._inner.asks_to_see(line, recent),
        )

    def shown_problem(
        self, line: str, recent: Sequence[Any], referent: str | None = None
    ) -> str | None:
        return neutral_on_error(
            self._subject,
            "followups.shown_problem",
            None,
            lambda: self._inner.shown_problem(line, recent, referent),
        )

    def changed_problem(
        self, problem: str, changes: Sequence[tuple[str | None, str]]
    ) -> str | None:
        return neutral_on_error(
            self._subject,
            "followups.changed_problem",
            None,
            lambda: self._inner.changed_problem(problem, changes),
        )

    def restates(self, problem: str, line: str) -> bool:
        return neutral_on_error(
            self._subject,
            "followups.restates",
            False,
            lambda: self._inner.restates(problem, line),
        )

    def states_new(self, problem: str, line: str) -> bool:
        return neutral_on_error(
            self._subject,
            "followups.states_new",
            False,
            lambda: self._inner.states_new(problem, line),
        )

    def takes_every_change(
        self, problem: str, rewritten: str, line: str, new: Sequence[str]
    ) -> bool:
        return neutral_on_error(
            self._subject,
            "followups.takes_every_change",
            False,
            lambda: self._inner.takes_every_change(problem, rewritten, line, new),
        )


class GuardedPhoto:
    """A subject's photo reader; a failing read leaves an ordinary photo turn."""

    def __init__(self, inner: SubjectPhoto, subject: str) -> None:
        self._inner = inner
        self._subject = subject

    async def read(
        self,
        content: str,
        *,
        image_attachments: list[tuple[str, str]],
        load_image: Callable[[str], Awaitable[tuple[str, bytes] | None]],
        settings: Settings,
        on_status: Callable[[str], Awaitable[None]] | None,
    ) -> PhotoReading:
        return await _neutral_async(
            self._subject,
            "photo.read",
            PhotoReading(None, content),
            lambda: self._inner.read(
                content,
                image_attachments=image_attachments,
                load_image=load_image,
                settings=settings,
                on_status=on_status,
            ),
        )


class GuardedTool:
    """A subject's model-tool checks; a failing check refuses the call (fails closed)."""

    def __init__(self, inner: SubjectTool, subject: str) -> None:
        self._inner = inner
        self._subject = subject

    def refuses(self, name: str, raw_args: Any, user_text: str) -> bool:
        return neutral_on_error(
            self._subject,
            "tool.refuses",
            True,
            lambda: self._inner.refuses(name, raw_args, user_text),
        )

    def call_matches(self, raw_args: Any, user_texts: list[str]) -> str | None:
        return neutral_on_error(
            self._subject,
            "tool.call_matches",
            None,
            lambda: self._inner.call_matches(raw_args, user_texts),
        )

    def draws_curve(self, fence: dict[str, Any] | None) -> bool:
        return neutral_on_error(
            self._subject, "tool.draws_curve", False, lambda: self._inner.draws_curve(fence)
        )

    def asks_for_earlier_curve(self, text: str) -> bool:
        return neutral_on_error(
            self._subject,
            "tool.asks_for_earlier_curve",
            False,
            lambda: self._inner.asks_for_earlier_curve(text),
        )


class GuardedFigure:
    """A subject's question figure; a failing member draws nothing."""

    def __init__(self, inner: SubjectFigure, subject: str) -> None:
        self._inner = inner
        self._subject = subject

    async def draw(
        self, question: str, earlier: Sequence[str], settings: Settings, *, asked: bool = True
    ) -> str | None:
        return await _neutral_async(
            self._subject,
            "figure.draw",
            None,
            lambda: self._inner.draw(question, earlier, settings, asked=asked),
        )

    def shown(self, verified: VerifiedSolveBlock | None) -> bool:
        # Shown already: nothing more is drawn.
        return neutral_on_error(
            self._subject, "figure.shown", True, lambda: self._inner.shown(verified)
        )

    def whole(self, text: str) -> bool:
        return neutral_on_error(
            self._subject, "figure.whole", True, lambda: self._inner.whole(text)
        )

    def adds_to(self, text: str, fence: str) -> bool:
        return neutral_on_error(
            self._subject, "figure.adds_to", False, lambda: self._inner.adds_to(text, fence)
        )

    def without_substitutes(self, text: str, fence: str) -> str:
        return neutral_on_error(
            self._subject,
            "figure.without_substitutes",
            text,
            lambda: self._inner.without_substitutes(text, fence),
        )

    def contract_for(self, question: str, asked: bool, *, graph: bool = False) -> str:
        return neutral_on_error(
            self._subject,
            "figure.contract_for",
            "",
            lambda: self._inner.contract_for(question, asked, graph=graph),
        )

    async def described(
        self,
        descriptions: Sequence[str],
        texts: Sequence[str],
        reply: str,
        settings: Settings,
        facts: GraphFactReader | None = None,
        problem: str | None = None,
        asked: bool = True,
    ) -> list[str]:
        return await _neutral_async(
            self._subject,
            "figure.described",
            [],
            lambda: self._inner.described(
                descriptions, texts, reply, settings, facts, problem, asked
            ),
        )

    def without_drawn_substitutes(self, text: str, user_text: str = "") -> str:
        return neutral_on_error(
            self._subject,
            "figure.without_drawn_substitutes",
            text,
            lambda: self._inner.without_drawn_substitutes(text, user_text),
        )


class GuardedFormal:
    """A subject's worked answer; a failing member answers nothing."""

    def __init__(self, inner: SubjectFormal, subject: str) -> None:
        self._inner = inner
        self._subject = subject

    async def answer(self, question: str, settings: Settings) -> FormalAnswer | None:
        return await _neutral_async(
            self._subject, "formal.answer", None, lambda: self._inner.answer(question, settings)
        )


class GuardedSubject:
    """A registered subject as chat asks it, each member answering neutrally if it raises."""

    def __init__(self, inner: SubjectAdapter) -> None:
        self._inner = inner
        self._followups = GuardedFollowups(inner.followups, inner.name)
        photo, tool, figure = inner.photo, inner.tool, inner.figure
        self._photo = GuardedPhoto(photo, inner.name) if photo is not None else None
        self._tool = GuardedTool(tool, inner.name) if tool is not None else None
        self._figure = GuardedFigure(figure, inner.name) if figure is not None else None
        formal = inner.formal
        self._formal = GuardedFormal(formal, inner.name) if formal is not None else None

    @property
    def name(self) -> SubjectName:
        return self._inner.name

    @property
    def hints(self) -> SubjectHints:
        return self._inner.hints

    @property
    def status_phase(self) -> str:
        return self._inner.status_phase

    @property
    def followups(self) -> GuardedFollowups:
        return self._followups

    @property
    def fence(self) -> SubjectFence:
        return self._inner.fence

    @property
    def photo(self) -> GuardedPhoto | None:
        return self._photo

    @property
    def tool(self) -> GuardedTool | None:
        return self._tool

    @property
    def figure(self) -> GuardedFigure | None:
        return self._figure

    @property
    def formal(self) -> GuardedFormal | None:
        return self._formal

    @property
    def graph_facts(self) -> GraphFactReader | None:
        # A reader the drawing runs in the SymPy pool, where a failure draws nothing.
        return self._inner.graph_facts

    def enabled(self, settings: Settings) -> bool:
        # Off: its lines go to the model, as with its switch off.
        return neutral_on_error(self.name, "enabled", False, lambda: self._inner.enabled(settings))

    def asks(self, text: str, *, has_image_attachment: bool = False) -> bool:
        return neutral_on_error(
            self.name,
            "asks",
            False,
            lambda: self._inner.asks(text, has_image_attachment=has_image_attachment),
        )

    def reads(self, text: str) -> bool:
        return neutral_on_error(self.name, "reads", False, lambda: self._inner.reads(text))

    def asks_of(self, setup: str, question: str) -> bool:
        return neutral_on_error(
            self.name, "asks_of", False, lambda: self._inner.asks_of(setup, question)
        )

    def fast_lane(self, text: str, *, tools_on: bool, claimed: bool = True) -> bool | None:
        return neutral_on_error(
            self.name,
            "fast_lane",
            None,
            lambda: self._inner.fast_lane(text, tools_on=tools_on, claimed=claimed),
        )

    def instant_reply(self, text: str, *, prior_reply: str | None) -> str | None:
        return neutral_on_error(
            self.name,
            "instant_reply",
            None,
            lambda: self._inner.instant_reply(text, prior_reply=prior_reply),
        )

    def warm(self) -> None:
        neutral_on_error(self.name, "warm", None, self._inner.warm)

    def solve_timeouts(self) -> AbstractContextManager[list[str]]:
        return neutral_on_error(
            self.name, "solve_timeouts", nullcontext([]), self._inner.solve_timeouts
        )

    async def solve(self, request: SubjectRequest, settings: Settings) -> SubjectAugmentation:
        # No subject: the model answers the line, and nothing is verified.
        return await _neutral_async(
            self.name,
            "solve",
            SubjectAugmentation(None, None, None),
            lambda: self._inner.solve(request, settings),
        )

    def direct_reply(
        self,
        verified: VerifiedSolveBlock,
        user_text: str,
        *,
        has_image_attachment: bool,
        verified_request_text: str | None,
    ) -> str | None:
        # No direct reply: the model writes it from the verified block.
        return neutral_on_error(
            self.name,
            "direct_reply",
            None,
            lambda: self._inner.direct_reply(
                verified,
                user_text,
                has_image_attachment=has_image_attachment,
                verified_request_text=verified_request_text,
            ),
        )
