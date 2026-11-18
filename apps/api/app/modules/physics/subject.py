"""Physics as the subject registry asks it (``services/subjects/registry``).

The adapter calls what physics already has: the verified block through ``prompt``, the
direct reply through ``direct``, and its prompt copy from ``reply_policy`` and ``followup``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from app.modules.physics.extract import needs_physics
from app.modules.physics.field_lines.contract import FIELD_DRAW_CONTRACT
from app.modules.physics.followup import (
    PHYSICS_FOLLOWUP_HINT,
    physics_followup_problem,
    physics_followup_whole,
    shown_physics_problem,
)
from app.modules.physics.prompt import build_physics_augmentation
from app.modules.physics.reply_policy import PHYSICS_REPLY_POLICY, physics_prompt_hints
from app.modules.turn_reading.see_request import asks_to_see
from app.services.graph_facts import GraphFactReader, GraphFacts
from app.services.solving import PhotoReading, SubjectAugmentation, VerifiedPhysicsBlock
from app.services.subject_hints import SubjectHints

if TYPE_CHECKING:
    from app.core.config import Settings
    from app.services.formal.answer import FormalAnswer
    from app.services.solving import VerifiedSolveBlock
    from app.services.subjects.registry import SubjectRequest


def _physics_request_text(user_content: str) -> str:
    """The problem a physics turn verifies.

    A scanned photo's caption is a protocol line. When the turn read the photo, that
    reading is the problem, whichever tab took it (a physics word problem on the maths
    tab); without one, the caption alone gets the unverified physics note.
    """
    from app.services.subject_scan import confirmed_scan_reading, scanner_camera_subject

    if scanner_camera_subject(user_content) is None:
        return user_content
    return confirmed_scan_reading(user_content) or user_content


_HINTS = SubjectHints(
    physics_prompt_hints,
    (PHYSICS_REPLY_POLICY,),
    shared_math_ink=False,
    followup=(PHYSICS_FOLLOWUP_HINT,),
    # Its words are rules the leak pass knows: the contract a field picture is described by.
    beside_visuals=(FIELD_DRAW_CONTRACT,),
)


@dataclass(frozen=True)
class PhysicsFollowups:
    def changed_problem(
        self, problem: str, changes: Sequence[tuple[str | None, str]]
    ) -> str | None:
        from app.modules.physics.followup import changed_physics_problem

        return changed_physics_problem(problem, changes)

    def restates(self, problem: str, line: str) -> bool:
        from app.modules.physics.followup import restates_physics_problem

        return restates_physics_problem(problem, line)

    def states_new(self, problem: str, line: str) -> bool:
        from app.modules.physics.followup import physics_states_new

        return physics_states_new(problem, line)

    def takes_every_change(
        self, problem: str, rewritten: str, line: str, new: Sequence[str]
    ) -> bool:
        from app.modules.physics.followup import physics_change_whole

        return physics_change_whole(problem, rewritten, line, new)

    def problem(
        self,
        query: str | None,
        recent: Sequence[Any],
        *,
        blocked: Callable[[str], bool] | None = None,
    ) -> str | None:
        return physics_followup_problem(query, recent)

    def continues(
        self,
        query: str | None,
        recent: Sequence[Any],
        *,
        blocked: Callable[[str], bool] | None = None,
    ) -> bool:
        return physics_followup_problem(query, recent) is not None

    def previous_result(self, reply: str) -> str | None:
        return None

    def continues_alone(self, line: str) -> bool:
        return False

    def borrows_earlier(self, line: str) -> bool:
        return False

    def asks_to_see(self, line: str, recent: Sequence[Any] | None = None) -> bool:
        return asks_to_see(line) and (recent is None or any(recent))

    def shown_problem(
        self, line: str, recent: Sequence[Any], referent: str | None = None
    ) -> str | None:
        return shown_physics_problem(line, referent)


@dataclass(frozen=True)
class PhysicsFence:
    """Physics checks the replies it verified (chat's finalize passes)."""

    def owns(self, verified: VerifiedSolveBlock | None) -> bool:
        return isinstance(verified, VerifiedPhysicsBlock)

    def needs_check(self, text: str, verified: VerifiedSolveBlock | None) -> bool:
        return True

    def check(
        self, text: str, verified: VerifiedSolveBlock | None, correct: bool, user_text: str
    ) -> str:
        from app.modules.physics.fence import validate_physics_fences

        return validate_physics_fences(
            text, verified=_physics_block(verified), correct=correct, user_text=user_text
        )

    def recover(self, text: str, verified: VerifiedSolveBlock | None) -> str:
        from app.modules.physics.fence import replace_unclosed_physics_fences_safe

        return replace_unclosed_physics_fences_safe(text, _physics_block(verified))

    def cards(self, verified: VerifiedSolveBlock) -> tuple[str, ...]:
        from app.modules.physics.fence import solver_cards

        block = _physics_block(verified)
        return solver_cards(block) if block is not None else ()

    def unverified_note(self, text: str) -> str:
        # An unverified physics turn's note is in its prompt, not under the reply.
        return text

    def draws(self, text: str, settings: Settings) -> bool:
        return False

    async def named(self, text: str, settings: Settings) -> dict[str, str]:
        return {}

    def draw(self, text: str, settings: Settings, named: Mapping[str, str] | None = None) -> str:
        return text

    def tidy(self, text: str, user_text: str, verified: VerifiedSolveBlock | None) -> str:
        return text


def _physics_block(verified: VerifiedSolveBlock | None) -> VerifiedPhysicsBlock | None:
    return verified if isinstance(verified, VerifiedPhysicsBlock) else None


@dataclass(frozen=True)
class PhysicsPhoto:
    """The problem on a physics scanner photo, read in the turn and stated as its confirmed line.

    The turn then solves it as a typed physics question; a read that finds nothing leaves the
    turn an ordinary photo turn.
    """

    async def read(
        self,
        content: str,
        *,
        image_attachments: list[tuple[str, str]],
        load_image: Callable[[str], Awaitable[tuple[str, bytes] | None]],
        settings: Settings,
        on_status: Callable[[str], Awaitable[None]] | None,
    ) -> PhotoReading:
        # Its reader has no certainty signal: a plain-text vision read, stated as the line.
        if not settings.physics_enabled:
            return PhotoReading(None, content)
        from app.modules.physics.read import read_physics_problem
        from app.services.subject_scan import read_scanned_problem

        async def read(content_type: str, data: bytes) -> str:
            return await read_physics_problem(settings, content_type=content_type, data=data)

        return PhotoReading(
            None,
            await read_scanned_problem(
                content,
                subject="physics",
                image_attachments=image_attachments,
                load_image=load_image,
                read=read,
                on_status=on_status,
            ),
        )


@dataclass(frozen=True)
class PhysicsFormal:
    """A physics question its solvers did not read: a model writes it down as maths and the
    server solves it (``physics.formal_read``); None unless the two answers agree."""

    async def answer(self, question: str, settings: Settings) -> FormalAnswer | None:
        from app.modules.physics import formal_read

        return await formal_read.formal_answer(question, settings)


def _read_graph_facts(text: str) -> GraphFacts:
    """Physics' reading of a question's words for maths' plot: its motion's v(t) and s(t)
    (``physics.graph_facts``). Picklable: maths runs it in the SymPy pool."""
    from app.modules.physics.graph_facts import read_graph_facts

    return read_graph_facts(text)


@dataclass(frozen=True)
class PhysicsFigure:
    """Physics' picture a reply describes: an electric field's lines (``field_lines``).

    Its other pictures come with its solve (a scene, a circuit, rays, a wave), so it draws
    nothing from a read of its own (``draw``), and a solve's turn already holds its picture
    (``shown``). On a physics message that asks to see a diagram no solve drew, the reply
    describes the field in a ```draw block (``contract``) and the server traces it
    (``described``); the model's own sketch of it then goes (``without_drawn_substitutes``).
    """

    async def draw(
        self, question: str, earlier: Sequence[str], settings: Settings, *, asked: bool = True
    ) -> str | None:
        return None

    def shown(self, verified: VerifiedSolveBlock | None) -> bool:
        # A physics solve draws its own picture, which no other figure adds to.
        return verified is not None

    def whole(self, text: str) -> bool:
        return True

    def adds_to(self, text: str, fence: str) -> bool:
        return False

    def without_substitutes(self, text: str) -> str:
        return text

    @property
    def contract(self) -> str:
        return FIELD_DRAW_CONTRACT

    async def described(
        self,
        descriptions: Sequence[str],
        texts: Sequence[str],
        reply: str,
        settings: Settings,
        facts: GraphFactReader | None = None,
    ) -> list[str]:
        from app.core import sympy_executor
        from app.modules.physics.field_lines.build import field_fences

        return await sympy_executor.run_sympy(
            field_fences,
            list(descriptions),
            list(texts),
            timeout=settings.stem_solve_timeout_seconds,
        )

    def without_drawn_substitutes(self, text: str, user_text: str = "") -> str:
        from app.modules.physics.sketches import without_model_drawings

        return without_model_drawings(text, user_text)


@dataclass(frozen=True)
class PhysicsSubject:
    name: Literal["physics"] = "physics"
    hints: SubjectHints = _HINTS
    status_phase: str = "physics"
    followups: PhysicsFollowups = PhysicsFollowups()
    fence: PhysicsFence = PhysicsFence()
    photo: PhysicsPhoto = PhysicsPhoto()
    # No model tool of its own.
    tool: None = None
    # Its pictures come with its solve (a scene, a circuit), never from a separate read; a
    # reply describes a field's lines, which the server traces (``field_lines``).
    figure: PhysicsFigure = PhysicsFigure()
    # A question its solvers did not read, written down as maths by a model and solved.
    formal: PhysicsFormal = PhysicsFormal()
    graph_facts: GraphFactReader | None = _read_graph_facts

    def enabled(self, settings: Settings) -> bool:
        return settings.physics_enabled

    def asks(self, text: str, *, has_image_attachment: bool = False) -> bool:
        return needs_physics(text)

    def reads(self, text: str) -> bool:
        from app.modules.physics.extract import extract_physics_intent

        return extract_physics_intent(text) is not None

    def asks_of(self, setup: str, question: str) -> bool:
        from app.modules.physics.extract import extract_physics_intent

        intent = extract_physics_intent(f"{setup} {question}")
        return intent is not None and bool(intent.asked)

    def fast_lane(self, text: str, *, tools_on: bool, claimed: bool = True) -> bool | None:
        # Its cues read a line whether or not the order gave it physics: "a pendulum's
        # period" with no numbers still wants the strong model.
        from app.modules.physics.lane import physics_fast_lane

        return physics_fast_lane(text, tools_on=tools_on, claimed=claimed)

    def instant_reply(self, text: str, *, prior_reply: str | None) -> str | None:
        return None

    def warm(self) -> None:
        return None

    def solve_timeouts(self) -> AbstractContextManager[list[str]]:
        return nullcontext([])

    async def solve(self, request: SubjectRequest, settings: Settings) -> SubjectAugmentation:
        block, physics_verified, solve_failed, unanswerable = await build_physics_augmentation(
            _physics_request_text(request.text),
            settings,
            needs_subject=True,
        )
        return SubjectAugmentation(
            subject="physics",
            prompt_block=block,
            verified=physics_verified,
            # No matching template is not a failed check. The prompt note still
            # tells the model not to claim a check. The reply does not say it
            # could not be verified.
            unverified=solve_failed,
            unanswerable=unanswerable,
        )

    def direct_reply(
        self,
        verified: VerifiedSolveBlock,
        user_text: str,
        *,
        has_image_attachment: bool,
        verified_request_text: str | None,
    ) -> str | None:
        if not isinstance(verified, VerifiedPhysicsBlock):
            return None
        if asks_to_see(user_text):
            from app.modules.physics.fence import scene_reply

            return scene_reply(verified)
        from app.modules.physics.direct import maybe_direct_physics_reply

        return maybe_direct_physics_reply(
            verified,
            solved_text(user_text, verified_request_text),
            has_image_attachment=has_image_attachment,
        )


def solved_text(user_text: str, followup_problem: str | None) -> str:
    """The text the verified result answers: the problem a follow-up rewrote ("what if the
    voltage doubled?" is "a resistance of 6 Ω and a voltage of 24 V, find the current"),
    when that problem is all the line asks; else the line, which the model answers with
    the verified result. "why?" wants the working explained, "and after 10 s, in km/h?"
    a unit the rewrite does not carry."""
    if followup_problem is None or not physics_followup_whole(user_text):
        return user_text
    return followup_problem


PHYSICS_SUBJECT = PhysicsSubject()
