"""Check-my-work block: the student's own lines, graded, and a reply to send.

The reply is rendered here rather than by the model, the same way equation
lessons are, so the verdict a student sees is exactly what SymPy checked. In
hint mode ("don't finish it for me") the reply names the line and the rule it
breaks as a question, and no corrected line or answer leaves this module.
"""

from __future__ import annotations

from app.core.config import Settings
from app.models.schemas.math import MathIntent
from app.modules.math.solve.key_steps import KeyStep
from app.modules.math.solve.work_check import WorkCheck, check_work
from app.services.solving import VerifiedMathBlock, _answer_canonical


def _verified_block_work_check(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not intent.work_lines:
        return None
    check = check_work(intent.work_lines, intent.variable)
    if check is None:
        return None
    hint_only = intent.work_hint_only
    lines.extend(_summary_lines(check, hint_only=hint_only))
    # A hint never carries the answer, unless the student already reached it.
    answer = check.answer if not hint_only or _correct_and_done(check) else None
    if answer:
        lines.append(f"Verified result: {answer}")
    return VerifiedMathBlock(
        text="\n".join(lines),
        canonical_fence=_answer_canonical(answer) if answer else None,
        canonical_answer=answer,
        direct_reply=format_work_check_reply(check, hint_only=hint_only),
    )


def _correct_and_done(check: WorkCheck) -> bool:
    return check.mistake is None and check.finished


def _verdict(check: WorkCheck, index: int) -> str:
    verdict = check.verdicts[index]
    if verdict == "given":
        return "(the problem)"
    if verdict == "ok":
        return "\u2713"
    if verdict == "carried" and check.mistake is not None:
        return f"follows, but carries the line {check.mistake.line} slip"
    return "\u2717"


def _graded_lines(check: WorkCheck) -> list[str]:
    return [
        f"**Line {index + 1}** {_verdict(check, index)}\n${tex}$"
        for index, tex in enumerate(check.lines)
    ]


def _numbered(steps: tuple[KeyStep, ...] | list[KeyStep]) -> list[str]:
    return [
        f"**{index}. {step.label}**\n${step.formula}$" for index, step in enumerate(steps, start=1)
    ]


def _answer_fence(answer: str) -> str:
    return f"```answer\n{answer}\n```"


def _lower_first(text: str) -> str:
    return text[:1].lower() + text[1:] if text else text


def format_work_check_reply(check: WorkCheck, *, hint_only: bool = False) -> str:
    chunks = _graded_lines(check)
    mistake = check.mistake
    if mistake is None:
        if check.finished:
            chunks.append("Every step checks out.")
            if check.check and not hint_only:
                chunks.append(f"Check: ${check.check}$")
            chunks.append(_answer_fence(check.answer))
        elif hint_only:
            nudge = "Everything so far is right."
            if check.steps:
                nudge += f" **Next move:** {_lower_first(check.steps[0].label)}."
            chunks.append(nudge)
        else:
            chunks.append("Everything so far is right. To finish:")
            chunks.extend(_numbered(check.steps))
            chunks.append(_answer_fence(check.answer))
        return "\n\n".join(chunks) + "\n"
    if hint_only:
        chunks.append(f"**Hint:** {mistake.hint}")
        return "\n\n".join(chunks) + "\n"
    chunks.append(f"**What went wrong in line {mistake.line}:** {mistake.explanation}")
    if check.steps:
        start = (
            f"**Fixed from line {mistake.line}:**"
            if mistake.fixed_tex is not None
            else f"**Starting again from line {mistake.line - 1}:**"
        )
        chunks.append(start)
        chunks.extend(_numbered(check.steps))
    chunks.append(_answer_fence(check.answer))
    return "\n\n".join(chunks) + "\n"


def _summary_lines(check: WorkCheck, *, hint_only: bool) -> list[str]:
    """The model-facing record, for turns that keep the model (an attachment)."""
    out = ["Student work check (each line compared with line 1 by SymPy):"]
    for index, tex in enumerate(check.lines):
        verdict = check.verdicts[index]
        note = {
            "given": "the problem as the student wrote it",
            "ok": "correct",
            "wrong": "FIRST MISTAKE",
            "carried": "follows from the line before (carries the mistake)",
            "off": "also wrong",
        }[verdict]
        out.append(f"Line {index + 1}: {tex} ({note})")
    mistake = check.mistake
    if mistake is not None:
        detail = mistake.hint if hint_only else mistake.explanation
        out.append(f"Mistake in line {mistake.line} ({mistake.kind}): {detail}")
        if mistake.fixed_tex and not hint_only:
            out.append(f"Corrected line {mistake.line}: {mistake.fixed_tex}")
    elif not check.finished:
        out.append("Every line is correct so far; the work is not finished.")
    if hint_only:
        out.append(
            "The student asked for a hint only: name the wrong line and ask about the rule it "
            "breaks. Do not state a corrected line or the solution."
        )
    return out
