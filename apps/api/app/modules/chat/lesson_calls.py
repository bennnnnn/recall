"""The two parts of a lesson the server asks a model for when the reply left them out.

A lesson's practice card (``LessonPractice``) and an outline's topics (``OutlineTopics``)
are written by a cheap model from the reply itself, validated with Pydantic (CLAUDE.md golden
rule 6) and laid out by the server (``lesson_shape``, ``lesson_outline``). A call that
fails, times out or returns something invalid gives None: the reply then stays as written.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Annotated, Self

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from app.gateways.structured_completion import complete_structured
from app.models.routing_lanes import ROUTING
from app.modules.chat.stream_status import announced_if_slow

if TYPE_CHECKING:
    from app.modules.chat.finalize_passes import FinalizeState

_REPLY_CHARS = 9000
_MESSAGE_CHARS = 600

Line = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
# Output on several lines, written as "3\\n2\\n1" or with real breaks: one line on the card.
_LINE_BREAKS = re.compile(r"\s*(?:\\n|\n)+\s*")


class QuizCard(BaseModel):
    """The ```quiz card the phone draws (``QuizCard.tsx``): pick an option, then check it.
    Its label is the server's (``LessonCopy.exercise``)."""

    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=400)]
    code: Annotated[str, StringConstraints(max_length=1500)] = ""
    options: list[Line] = Field(min_length=3, max_length=5)
    answer: int = Field(ge=0)
    explanation: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=3, max_length=700)
    ]

    @field_validator("options", mode="after")
    @classmethod
    def _one_line_each(cls, options: list[str]) -> list[str]:
        return [_LINE_BREAKS.sub(", ", option) for option in options]

    @model_validator(mode="after")
    def _one_right_option(self) -> Self:
        if self.answer >= len(self.options):
            raise ValueError("answer is not an option")
        if len({option.casefold() for option in self.options}) != len(self.options):
            raise ValueError("options repeat")
        return self


class LessonPractice(BaseModel):
    topic: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    quiz: QuizCard


_PRACTICE_SYSTEM = (
    "You write the practice card that ends a lesson. Read the lesson and write ONE "
    "multiple-choice question that checks its key idea, in the language the lesson is "
    "written in. If the lesson ends by asking the learner a practice question or exercise, "
    "turn that one into the card. For code, prefer 'What will this code print?' or 'What "
    "should it return?', with the code it needs in `code` (lines joined with \\n) and never "
    "repeated in the question; otherwise `code` is empty. Give 3 or 4 short options; make "
    "the wrong ones real mistakes a learner makes. `answer` is the 0-based index of the one "
    "right option; each option is one line (output on several lines as '3, 2, 1'). "
    "`explanation` says why in one or two sentences. `topic` names what the lesson teaches "
    "in 1 to 5 words, in the lesson's language. Plain text, no LaTeX. Return JSON: "
    '{"topic": ..., "quiz": {"question": ..., "code": ..., "options": [...], "answer": ..., '
    '"explanation": ...}}.'
)


def _messages(system: str, state: FinalizeState, reply: str) -> list[dict[str, str]]:
    asked = (state.ctx.user_message_content or "")[:_MESSAGE_CHARS]
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"THE LEARNER ASKED:\n{asked}\n\nTHE REPLY:\n{reply}"},
    ]


async def _ask[T: BaseModel](
    state: FinalizeState, system: str, schema: type[T], max_tokens: int
) -> T | None:
    settings = state.settings
    return await announced_if_slow(
        complete_structured(
            settings=settings,
            model_alias=ROUTING.background,
            messages=_messages(system, state, state.text[:_REPLY_CHARS]),
            schema=schema,
            max_tokens=max_tokens,
            timeout_seconds=settings.lesson_shape_timeout_seconds,
            usage=state.usage,
            allow_fallback=False,
            fallback_on_invalid=True,
        ),
        state.on_status,
        "composing",
        then="finishing",
    )


async def lesson_practice(state: FinalizeState) -> LessonPractice | None:
    """A practice card for the lesson in ``state.text``, or None."""
    return await _ask(state, _PRACTICE_SYSTEM, LessonPractice, 900)
