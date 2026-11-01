"""The subjects a turn is solved by, each plugged in through one adapter (structure ticket ST-07).

A subject (maths, physics, chemistry) owns one ``SubjectAdapter`` in its public ``subject``
file, and ``SUBJECTS`` below names it in one entry, as ``services/mcp`` registers the model's
tools. The dispatcher (``services/subjects/dispatch``) asks a subject through its adapter, never
through the subject's own files. Which subject a line is belongs to the subject order
(``services/subjects/order``), the one place precedence between subjects is written: the order
of ``SUBJECTS`` decides nothing.

An adapter has what the dispatcher and chat ask of every subject:

- ``name``: the subject, one of ``SubjectName``;
- ``solve``: the turn's verified block for a line, the prompt note when nothing verified it,
  and whether the subject tried and declined (``SubjectAugmentation``);
- ``direct_reply``: the reply a verified block may show without a model, or None. It runs in
  the SymPy pool (its checks parse with SymPy);
- ``hints``: its prompt copy, and where chat states it (``SubjectHints``);
- ``asks``: whether a line asks something of the subject (its cue), solved or not;
- ``followups``: how it reads a line that goes back to its last problem
  (``SubjectFollowups``). A subject with nothing to read there answers None or False.

A new subject is a module with its own ``subject`` adapter, its name in ``SubjectName`` (in
``services/solving``, beside the verified block every subject's solve names itself in) and its
entry in ``SUBJECTS``; ``tests/services/test_subject_registry.py`` holds the two to each other.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from app.modules.chemistry.subject import CHEMISTRY_SUBJECT
from app.modules.math.subject import MATH_SUBJECT
from app.modules.physics.subject import PHYSICS_SUBJECT
from app.services.solving import SubjectName as SubjectName

if TYPE_CHECKING:
    from redis.asyncio import Redis

    from app.core.config import Settings
    from app.modules.math.schemas import MathImageExtract
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

    def asks_to_see(self, line: str, recent: Sequence[Any] | None = None) -> bool:
        """A cheap look, on the loop: the line asks to see what the subject's card draws,
        and, given the chat's recent lines, one of them could be the problem it draws."""
        ...

    def shown_problem(self, line: str, recent: Sequence[Any]) -> str | None:
        """The problem whose card draws what the line asks to see, read in the pool."""
        ...


class SubjectAdapter(Protocol):
    """One subject, as the dispatcher and chat ask it."""

    @property
    def name(self) -> SubjectName: ...

    @property
    def hints(self) -> SubjectHints: ...

    @property
    def followups(self) -> SubjectFollowups: ...

    def asks(self, text: str, *, has_image_attachment: bool = False) -> bool: ...

    async def solve(self, request: SubjectRequest, settings: Settings) -> SubjectAugmentation: ...

    def direct_reply(
        self,
        verified: VerifiedSolveBlock,
        user_text: str,
        *,
        has_image_attachment: bool,
        verified_request_text: str | None,
    ) -> str | None: ...


# The registration: one entry per subject.
SUBJECTS: tuple[SubjectAdapter, ...] = (
    MATH_SUBJECT,
    PHYSICS_SUBJECT,
    CHEMISTRY_SUBJECT,
)

_BY_NAME: dict[SubjectName, SubjectAdapter] = {adapter.name: adapter for adapter in SUBJECTS}


def subject_adapter(name: SubjectName) -> SubjectAdapter:
    """The registered adapter of a subject."""
    return _BY_NAME[name]
