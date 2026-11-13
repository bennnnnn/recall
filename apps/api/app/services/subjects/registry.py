"""The subjects a turn is solved by, each plugged in through one adapter (structure ticket ST-07).

A subject (maths, physics, chemistry) owns one ``SubjectAdapter`` in its public ``subject``
file, and ``SUBJECTS`` below names it in one entry, as ``services/mcp`` registers the model's
tools. The dispatcher (``services/subjects/dispatch``) asks a subject through its adapter, never
through the subject's own files. Which subject a line is belongs to the subject order
(``services/subjects/order``), the one place precedence between subjects is written: the order
of ``SUBJECTS`` decides nothing.

An adapter has what the dispatcher and chat ask of every subject:

- ``name``: the subject, one of ``SubjectName``;
- ``enabled``: whether its settings switch is on, so chat solves its lines;
- ``status_phase``: the status line its solve shows (one of chat's ``StreamStatusPhase``,
  each of which the phone has a label for);
- ``solve``: the turn's verified block for a line, the prompt note when nothing verified it,
  and whether the subject tried and declined (``SubjectAugmentation``);
- ``direct_reply``: the reply a verified block may show without a model, or None. It runs in
  the SymPy pool (its checks parse with SymPy);
- ``hints``: its prompt copy, and where chat states it (``SubjectHints``);
- ``asks``: whether a line asks something of the subject (its cue), solved or not;
- ``reads``: whether the subject reads a request out of the line (its intent);
- ``fast_lane``: the model lane its own read of a line suggests to Auto routing, for a line
  the subject order gave it and for one no subject claimed;
- ``instant_reply``: a reply the subject writes for a line with no model and no solve;
- ``warm``: what a fresh SymPy pool worker runs first, so a turn pays no imports;
- ``solve_timeouts``: the solves of the subject that ran out of time inside a block;
- ``photo``: how it reads its problem off a turn's photo (``SubjectPhoto``), or None;
- ``tool``: how the tool loop checks calls to the model tool it owns (``SubjectTool``), or
  None;
- ``figure``: the picture it draws for a question that asks to see one, from the question's
  own values (``SubjectFigure``), or None;
- ``followups``: how it reads a line that goes back to its last problem
  (``SubjectFollowups``);
- ``fence``: which verified blocks it finishes, how it holds a finished reply's fences to
  its block, and the notes, drawings and clean-up it adds (``SubjectFence``).

A subject with nothing to offer for a member answers None or False, or returns the text as it is.

Money is registered beside them as a peer (``MONEY``, a ``MoneyPeer``): a loan, card or
savings question is worked before the prompt and gets its calculator card after the reply,
and a money turn has no subject solve (chat's ``turn_prep``).

A new subject is a module with its own ``subject`` adapter, its name in ``SubjectName`` (in
``services/solving``, beside the verified block every subject's solve names itself in), its
entry in ``SUBJECTS`` and its step in the subject order; chat asks it through the adapter
from there. ``tests/services/test_subject_registry.py`` holds the names to each other and
``test_subject_completeness.py`` each adapter to what chat asks of it.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, TypeGuard

from app.modules.chemistry.subject import CHEMISTRY_SUBJECT

# What maths read off a photo: chat holds it for the turn and hands it back (``photo``).
from app.modules.math.schemas import MathImageExtract as MathImageExtract
from app.modules.math.subject import MATH_SUBJECT
from app.modules.money.subject import MONEY_PEER
from app.modules.physics.subject import PHYSICS_SUBJECT
from app.services.solving import SubjectName as SubjectName

if TYPE_CHECKING:
    from redis.asyncio import Redis

    from app.core.config import Settings
    from app.models.orm import User

    # A money turn, from its prompt to its finalize; chat holds it for the turn.
    from app.modules.money.service import MoneyTurn as MoneyTurn
    from app.services.solving import SubjectAugmentation, VerifiedSolveBlock
    from app.services.subject_hints import SubjectHints


@dataclass(frozen=True, kw_only=True)
class SubjectRequest:
    """One line a subject is asked to solve, and what the turn knows beside it."""

    # The line the subject reads: the message, its solve part, or a follow-up's problem.
    text: str
    # The line maths reads: a maths follow-up's earlier problem, otherwise ``text``.
    math_text: str
    has_image_attachment: bool = False
    # What maths read off a photo, when the turn has one.
    image_math_extract: MathImageExtract | None = None
    prior_user_messages: list[str] | None = None
    # The follow-up whose wording asks for the answer's shape ("how?", "graph it").
    response_intent_text: str | None = None
    redis: Redis | None = None


class SubjectFollowups(Protocol):
    """How a subject reads a line that goes back to its last problem."""

    def problem(
        self,
        query: str | None,
        recent: Sequence[Any],
        *,
        blocked: Callable[[str], bool] | None = None,
    ) -> str | None:
        """The earlier problem this line asks again about ("how?", "what about 2 moles?").

        ``blocked`` names a line maths must not replay (a physics or chemistry problem).
        """
        ...

    def continues(
        self,
        query: str | None,
        recent: Sequence[Any],
        *,
        blocked: Callable[[str], bool] | None = None,
    ) -> bool:
        """The line only continues the subject's last exchange: its follow-up hints apply."""
        ...

    def previous_result(self, reply: str) -> str | None:
        """The last reply as the prompt shows it to a follow-up, or None to keep it as is."""
        ...

    def continues_alone(self, line: str) -> bool:
        """The line alone continues the subject's last problem ("graph it"), no exchange read."""
        ...

    def borrows_earlier(self, line: str) -> bool:
        """The subject may solve the line from the user's earlier lines ("graph it", or a
        fragment such as "5" that continues an open equation): a gate on what the readers
        read (``chat/whole_question``) holds those lines to it too."""
        ...

    def asks_to_see(self, line: str, recent: Sequence[Any] | None = None) -> bool:
        """A cheap look, on the loop: the line asks to see what the subject's card draws,
        and, given the chat's recent lines, one of them could be the problem it draws."""
        ...

    def shown_problem(
        self, line: str, recent: Sequence[Any], referent: str | None = None
    ) -> str | None:
        """The problem whose card draws what the line asks to see, read in the pool.
        ``referent``: the earlier message a model read as the "it" the line asks to see
        (``chat.referent_read``), when the turn read one."""
        ...

    def changed_problem(self, problem: str, given: str | None, new: str) -> str | None:
        """``problem`` with one given put to ``new``, the value a line changes it to ("what
        if it took 10 s?" is ``new`` "10 s"); ``given`` names which, as a model read it
        (``chat.posed_read``). None when the subject cannot put it in place exactly. Read
        in the pool."""
        ...


class SubjectFence(Protocol):
    """How a subject finishes a reply: chat's finalize passes ask it, in their order.

    ``check`` and ``draw`` take positional arguments: the SymPy pool runs them.
    """

    def owns(self, verified: VerifiedSolveBlock | None) -> bool:
        """Whether this subject finishes a reply whose turn ``verified`` stands for: a block
        of its own. Maths also finishes every reply no subject verified (None)."""
        ...

    def needs_check(self, text: str, verified: VerifiedSolveBlock | None) -> bool:
        """Whether ``check`` has anything to do, before the pool is asked."""
        ...

    def check(
        self, text: str, verified: VerifiedSolveBlock | None, correct: bool, user_text: str
    ) -> str:
        """The reply's fences held to the verified block. ``correct`` adds a correction
        line when model prose states a different value; the server never corrects its own."""
        ...

    def recover(self, text: str, verified: VerifiedSolveBlock | None) -> str:
        """``check`` failed or ran out of time: the fences closed and made safe, no solver."""
        ...

    def cards(self, verified: VerifiedSolveBlock) -> tuple[str, ...]:
        """The fences the subject writes for the block's result: its answer card and its
        pictures. A question in parts keeps the fences that are one of its parts' own."""
        ...

    def unverified_note(self, text: str) -> str:
        """The reply with the note an answer the subject could not verify carries."""
        ...

    def draws(self, text: str, settings: Settings) -> bool:
        """The reply holds fences the subject draws from its own data (``draw``)."""
        ...

    def draw(self, text: str, settings: Settings) -> str:
        """Those fences drawn, in the pool: a chart's formula sampled, a molecule's data."""
        ...

    def tidy(self, text: str, user_text: str, verified: VerifiedSolveBlock | None) -> str:
        """What the subject's prompt forbids and a reply still wrote, taken out."""
        ...


class SubjectPhoto(Protocol):
    """How a subject reads its problem off a turn's photo."""

    async def read(
        self,
        content: str,
        *,
        image_attachments: list[tuple[str, str]],
        load_image: Callable[[str], Awaitable[bytes | None]],
        settings: Settings,
        on_status: Callable[[str], Awaitable[None]] | None,
    ) -> tuple[MathImageExtract | None, str]:
        """What it read, and ``content`` with the line the prompt states it in.

        ``load_image`` gives a photo's bytes by its storage key.
        """
        ...


class SubjectTool(Protocol):
    """How the tool loop checks calls to the model tool a subject owns.

    ``call_matches`` and ``asks_for_earlier_curve`` take positional arguments: the SymPy
    pool runs them.
    """

    def refuses(self, name: str, raw_args: Any, user_text: str) -> bool:
        """A call that must not run for this problem (a solve that drops its domain)."""
        ...

    def call_matches(self, raw_args: Any, user_texts: list[str]) -> str | None:
        """The user's line (``user_texts`` newest first) whose problem the call works on, or
        None: chat holds that line to what the readers read (``turn_reading.readable``)."""
        ...

    def draws_curve(self, fence: dict[str, Any] | None) -> bool:
        """The call's fence is a sampled curve, not an answer or a diagram."""
        ...

    def asks_for_earlier_curve(self, text: str) -> bool:
        """A graph ask whose own words hold no formula: its curve is from earlier in the chat."""
        ...


class SubjectFigure(Protocol):
    """The picture a subject draws for a question that asks to see one (a figure, a graph,
    a number line), from the question's own values; started beside the reply and added
    after it when the reply holds no picture of the server's."""

    async def draw(self, question: str, earlier: Sequence[str], settings: Settings) -> str | None:
        """The picture's fence, or None when nothing is drawn. ``earlier``: the user's
        earlier messages, newest first, for a request to draw "it"."""
        ...

    def shown(self, verified: VerifiedSolveBlock | None) -> bool:
        """The turn's verified block already draws the whole picture."""
        ...

    def whole(self, text: str) -> bool:
        """The reply already holds a picture no figure adds to (a graph, a scene)."""
        ...

    def adds_to(self, text: str, fence: str) -> bool:
        """``fence`` shows what the reply's own pictures do not."""
        ...

    def without_substitutes(self, text: str, question: str) -> str:
        """``text`` without the model's own picture in characters, or a flowchart in its
        place that ``question`` did not ask for."""
        ...


class SubjectAdapter(Protocol):
    """One subject, as the dispatcher and chat ask it."""

    @property
    def name(self) -> SubjectName: ...

    @property
    def hints(self) -> SubjectHints: ...

    @property
    def status_phase(self) -> str: ...

    def enabled(self, settings: Settings) -> bool:
        """The subject's switch: chat solves its lines only while it is on."""
        ...

    @property
    def followups(self) -> SubjectFollowups: ...

    @property
    def fence(self) -> SubjectFence: ...

    def asks(self, text: str, *, has_image_attachment: bool = False) -> bool: ...

    def reads(self, text: str) -> bool: ...

    def asks_of(self, setup: str, question: str) -> bool:
        """The question asks something of the problem ``setup`` states, so it is read with
        it: "How long does it take to land?" after "A ball is dropped from 20 m", not "Who
        won the Arsenal game last night?"."""
        ...

    def fast_lane(self, text: str, *, tools_on: bool, claimed: bool = True) -> bool | None:
        """True keeps the line on the fast model (the verified answer needs no reasoning),
        False sends it to the strong one, None when the subject has no say. ``claimed``:
        the subject order gave the line to this subject; False asks whether the subject's
        own cues claim a line no subject did ("a pendulum's period" goes to the strong
        model)."""
        ...

    def instant_reply(self, text: str, *, prior_reply: str | None) -> str | None: ...

    def warm(self) -> None: ...

    def solve_timeouts(self) -> AbstractContextManager[list[str]]: ...

    @property
    def photo(self) -> SubjectPhoto | None: ...

    @property
    def tool(self) -> SubjectTool | None: ...

    @property
    def figure(self) -> SubjectFigure | None: ...

    async def solve(self, request: SubjectRequest, settings: Settings) -> SubjectAugmentation: ...

    def direct_reply(
        self,
        verified: VerifiedSolveBlock,
        user_text: str,
        *,
        has_image_attachment: bool,
        verified_request_text: str | None,
    ) -> str | None: ...


class MoneyPeer(Protocol):
    """Money as chat asks it: worked before the prompt, carded after the reply."""

    async def prepare(
        self,
        text: str,
        settings: Settings,
        redis: Redis | None,
        *,
        user: User | None,
        location: str | None,
        earlier: Sequence[str | Sequence[str]],
        last_reply: str,
    ) -> MoneyTurn | None:
        """The money turn ``text`` asks for, or None when it is not one."""
        ...

    async def prepare_standing(
        self,
        text: str,
        settings: Settings,
        redis: Redis | None,
        *,
        user: User | None,
        location: str | None,
        earlier: Sequence[str | Sequence[str]],
        last_reply: str,
    ) -> MoneyTurn | None:
        """The chat's earlier loan, for a message about it that is no money request itself."""
        ...

    async def finish(self, turn: MoneyTurn, text: str, settings: Settings, *, english: bool) -> str:
        """The reply with the market note and the calculator card under it."""
        ...

    def owns(self, value: object) -> TypeGuard[MoneyTurn]:
        """``value`` is a money turn."""
        ...


# Money, the subjects' peer.
MONEY: MoneyPeer = MONEY_PEER

# The registration: one entry per subject. Which subject a line is never follows this order
# (the subject order does); chat states the subjects' fixed prompt copy in it, which the
# leak pass joins as listed (``chat.prompt_subjects``).
SUBJECTS: tuple[SubjectAdapter, ...] = (
    PHYSICS_SUBJECT,
    MATH_SUBJECT,
    CHEMISTRY_SUBJECT,
)

_BY_NAME: dict[str, SubjectAdapter] = {adapter.name: adapter for adapter in SUBJECTS}

# The subject that finishes a reply no subject's fence owns: maths holds every unverified
# reply's answer fences, LaTeX and charts to what it can check (chat's finalize passes).
FENCE_FALLBACK: SubjectName = "math"


def subject_adapter(name: SubjectName) -> SubjectAdapter:
    """The registered adapter of a subject."""
    return _BY_NAME[name]


def adapter_named(name: str | None) -> SubjectAdapter | None:
    """The adapter of a subject named by a string a turn carries, or None for no subject."""
    return _BY_NAME.get(name) if name is not None else None


def fence_owner(verified: VerifiedSolveBlock | None) -> SubjectAdapter:
    """The subject that finishes a reply whose turn ``verified`` stands for: the one whose
    fence owns the block (one at most), else maths."""
    for adapter in SUBJECTS:
        if adapter.fence.owns(verified):
            return adapter
    return _BY_NAME[FENCE_FALLBACK]
