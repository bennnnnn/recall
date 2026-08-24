"""Prompt inject + camera extract → MathIntent."""

from __future__ import annotations

import logging
from typing import Literal, cast

from app.core.config import Settings
from app.models.math_schemas import (
    MathImageExtract,
    MathIntent,
)
from app.services import math_service
from app.services.math_tools.block import VerifiedMathBlock
from app.services.math_tools.extract import extract_math_intent
from app.services.prompt_inject import inject_before_last_user

logger = logging.getLogger(__name__)


def needs_symbolic_math(text: str, *, has_image_attachment: bool = False) -> bool:
    from app.services import math_text_match

    return math_text_match.needs_symbolic(text, has_image_attachment=has_image_attachment)


def _intent_from_image_extract(extract: MathImageExtract) -> MathIntent | None:
    """Map a vision extract onto an existing MathIntent kind (no second parser)."""
    variable = extract.variables[0]
    if extract.kind == "system" and extract.equations:
        return MathIntent(
            kind="system",
            system_equations=extract.equations[:4],
            system_variables=extract.variables,
            operation="solve",
        )
    if extract.kind == "inequality" and extract.comparator:
        return MathIntent(
            kind="inequality",
            lhs=extract.lhs,
            rhs=extract.rhs,
            comparator=extract.comparator,
            operation="solve",
            variable=variable,
        )
    if extract.kind == "calculus" and extract.expr and extract.operation:
        return MathIntent(
            kind="calculus",
            expr=extract.expr,
            operation=cast(
                Literal["simplify", "differentiate", "integrate", "factor", "expand"],
                extract.operation,
            ),
            variable=variable,
            integral_lower=extract.integral_lower,
            integral_upper=extract.integral_upper,
        )
    if extract.kind == "limit" and extract.expr and extract.limit_point:
        return MathIntent(
            kind="limit",
            expr=extract.expr,
            limit_point=extract.limit_point,
            operation="limit",
            variable=variable,
        )
    if extract.kind == "graph" and extract.expr:
        return MathIntent(
            kind="graph",
            expr=extract.expr,
            operation="graph",
            variable=variable,
        )
    if extract.kind == "rectangle" and extract.width is not None and extract.height is not None:
        return MathIntent(
            kind="rectangle",
            width=extract.width,
            height=extract.height,
            unit=extract.unit or "cm",
            wants_area=True,
            wants_perimeter=True,
        )
    if extract.kind == "circle" and extract.radius is not None:
        return MathIntent(
            kind="circle",
            radius=extract.radius,
            unit=extract.unit or "cm",
            wants_area=True,
            wants_circumference=True,
        )
    if (
        extract.kind == "triangle_sides"
        and extract.tri_a is not None
        and extract.tri_b is not None
        and extract.tri_c is not None
    ):
        return MathIntent(
            kind="triangle_sides",
            tri_a=extract.tri_a,
            tri_b=extract.tri_b,
            tri_c=extract.tri_c,
            unit=extract.unit or "cm",
            operation="solve",
        )
    if extract.kind == "statistics" and extract.stats_numbers and extract.stats_op:
        return MathIntent(
            kind="statistics",
            stats_op=cast(
                Literal["mean", "median", "mode", "variance", "stdev"],
                extract.stats_op,
            ),
            stats_numbers=extract.stats_numbers,
            operation="solve",
        )
    return MathIntent(
        kind="equation",
        lhs=extract.lhs,
        rhs=extract.rhs,
        operation="solve",
        variable=variable,
    )


async def build_math_augmentation(
    user_content: str,
    settings: Settings,
    *,
    has_image_attachment: bool = False,
    image_math_extract: MathImageExtract | None = None,
    needs_math: bool | None = None,
) -> tuple[str | None, VerifiedMathBlock | None]:
    """Compute the verified-math system block (or None) without mutating messages.

    Safe to run concurrently with web-search augmentation on the same base
    prompt — the caller injects returned blocks after gather.

    ``needs_math`` lets a caller that already evaluated the math-intent signal
    (e.g. prompt_builder uses it to gate the "calculating" status) pass it
    through so the same message isn't scanned twice per turn. When None,
    needs_symbolic_math is evaluated here (the historical behavior, kept for
    any caller that doesn't pre-compute it).
    """
    if not settings.math_tools_enabled:
        return None, None
    if needs_math is None:
        needs_math = needs_symbolic_math(user_content, has_image_attachment=has_image_attachment)
    if not needs_math:
        return None, None

    if image_math_extract is not None:
        # OCR already produced a Pydantic-validated extract — map it straight
        # to MathIntent (do not re-parse through the text regex, which mangles
        # unicode ops / abs bars a photographed problem can contain).
        intent = _intent_from_image_extract(image_math_extract)
    else:
        intent = extract_math_intent(user_content)
    if intent is None and has_image_attachment:
        lines = [
            "The user attached an image that may contain a math problem. "
            "Extract the equation as lhs/rhs if possible, then explain carefully. "
            "Do NOT claim SymPy verification unless a verified system block is present. "
            "Use $...$ for formulas. Do not emit ```geometry / ```graph — "
            "Recall attaches verified diagrams when measures are known. "
            "Never invent measures."
        ]
        return "\n".join(lines), None

    if intent is None:
        return _unverified_math_note("unknown"), None

    from app.services import math_tools as mt

    verified = await mt._build_verified_block_async(intent, settings)
    if not verified:
        # Intent matched but SymPy timed out / rejected / had no builder result.
        # Inject honesty so the model does not reuse the same "verified" UX.
        return _unverified_math_note(intent.kind), None
    return verified.text, verified


def _unverified_math_note(kind: str) -> str:
    """System note when symbolic intent fired but no VerifiedMathBlock landed."""
    return (
        "Math note: a symbolic problem was detected "
        f"(kind={kind}), but SymPy could not produce a verified result "
        "(timeout, unsupported expression, or incomplete extract).\n"
        "Explain carefully and show your work. Do NOT claim the answer was "
        "SymPy-verified. Write the result in `$...$` and mark uncertainty when "
        "you are unsure. Do NOT emit ```answer, ```geometry, or ```graph. "
        "Do not invent geometry/graph dimensions or point lists."
    )


async def augment_prompt_messages(
    messages: list[dict[str, str]],
    user_content: str,
    settings: Settings,
    *,
    has_image_attachment: bool = False,
    image_math_extract: MathImageExtract | None = None,
) -> tuple[list[dict[str, str]], VerifiedMathBlock | None]:
    block, verified = await build_math_augmentation(
        user_content,
        settings,
        has_image_attachment=has_image_attachment,
        image_math_extract=image_math_extract,
    )
    if block is None:
        return messages, None
    return inject_before_last_user(messages, block), verified


async def _build_verified_block_async(
    intent: MathIntent, settings: Settings
) -> VerifiedMathBlock | None:
    """Run the sync, CPU-bound SymPy work in a bounded subprocess with a
    hard timeout + SIGTERM on timeout.

    ``_build_verified_block`` calls into SymPy's ``solve``/``integrate``/etc.,
    which are synchronous and can take arbitrarily long on a pathological
    expression. Running them on the shared default ``asyncio.to_thread`` pool
    would (a) starve unrelated async work and (b) leak the thread on timeout
    (the await cancels but the thread keeps running). The bounded
    ``ProcessPoolExecutor`` isolates SymPy to a single subprocess that can be
    hard-killed on timeout.
    """
    from app.services import math_tools as mt
    from app.services.sympy_executor import run_sympy

    try:
        return await run_sympy(
            mt._build_verified_block,
            intent,
            settings,
            timeout=settings.math_solve_timeout_seconds,
        )
    except TimeoutError:
        logger.warning(
            "math_tools solve timed out after %ss for kind=%s",
            settings.math_solve_timeout_seconds,
            intent.kind,
        )
        return None
    except math_service.MathServiceError as exc:
        # Sync builder also catches this; keep the async boundary honest if a
        # patched/edge path raises through the executor.
        logger.info("math_tools skipped: %s", exc)
        return None
    except Exception:
        # BrokenProcessPool / cancelled sibling futures after another caller's
        # timeout kill — degrade to the honesty note, do not fail the turn.
        logger.warning(
            "math_tools solve failed for kind=%s",
            intent.kind,
            exc_info=True,
        )
        return None
