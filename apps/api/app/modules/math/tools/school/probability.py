"""Probability extractor and verified block."""

from __future__ import annotations

import math
import re
from dataclasses import replace
from fractions import Fraction

from app.core.config import Settings
from app.models.schemas.math import MathIntent
from app.modules.math import school as math_school
from app.modules.math.tools.block import VerifiedMathBlock, _finish_with_answer
from app.modules.math.tools.school._parse import _PROB_NUMBER

_BINOMIAL_PARAM = re.compile(
    rf"\b([nkp])\s*=\s*({_PROB_NUMBER}(?:\s*/\s*{_PROB_NUMBER})?)(?=\s|[,;.!?]|$)",
    re.IGNORECASE,
)
_PROBABILITY_LIST = re.compile(r"\[([^\[\]]+)\]")
_DICE_CONDITIONAL_SUM = re.compile(
    r"^\s*(?:two|2)\s+fair\s+dice\s+are\s+(?:rolled|thrown)\s*[.,;]?\s*"
    r"(?:given|knowing)(?:\s+that)?\s+(?:the\s+)?sum\s+is\s+"
    r"(at\s+least|at\s+most|greater\s+than|less\s+than|exactly|equal\s+to)\s+"
    r"(\d{1,2})\s*[.,;?]?\s*"
    r"(?:what\s+is|find|calculate|compute)\s+(?:the\s+)?probability"
    r"(?:\s+(?:that|of))?\s+(?:the\s+)?sum\s+is\s+(?:exactly|equal\s+to)\s+"
    r"(\d{1,2})"
    r"(?:\s*[?.]\s*(?:show|list)(?:\s+me)?(?:\s+the)?\s+conditional\s+"
    r"sample\s+space)?\s*[?.]?\s*$",
    re.IGNORECASE,
)


def _extract_probability_intent(cleaned: str) -> MathIntent | None:
    from app.modules.math.tools.extractors.formulas import extract_probability_formulas

    extra = extract_probability_formulas(cleaned)
    if extra is not None:
        return extra
    dice = _DICE_CONDITIONAL_SUM.fullmatch(cleaned)
    if dice is not None:
        relation, threshold_text, event_text = dice.groups()
        threshold, event = int(threshold_text), int(event_text)
        if 2 <= threshold <= 12 and 2 <= event <= 12:
            comparator = {
                "at least": ">=",
                "at most": "<=",
                "greater than": ">",
                "less than": "<",
                "exactly": "=",
                "equal to": "=",
            }[" ".join(relation.lower().split())]
            return MathIntent(
                kind="probability",
                school_op="dice_conditional_sum",
                comparator=comparator,
                combo_n=threshold,
                combo_k=event,
                operation="solve",
            )
    lower = cleaned.lower()
    if "binomial" in lower or ("n=" in lower.replace(" ", "") and "p=" in lower.replace(" ", "")):
        empty = MathIntent(kind="probability", school_op="binomial", operation="solve")
        matches = list(_BINOMIAL_PARAM.finditer(cleaned))
        if len(matches) != 3 or {match.group(1).lower() for match in matches} != {"n", "k", "p"}:
            return empty
        try:
            params = {
                match.group(1).lower(): float(Fraction(match.group(2).replace(" ", "")))
                for match in matches
            }
        except (ValueError, ZeroDivisionError, OverflowError):
            return empty
        n, k, p = params["n"], params["k"], params["p"]
        if n is not None and k is not None and p is not None:
            if not n.is_integer() or not k.is_integer():
                return empty
            return MathIntent(
                kind="probability",
                school_op="binomial",
                combo_n=int(n),
                combo_k=int(k),
                percent_base=p,
                operation="solve",
            )
    if "expected value" in lower or "expected value of" in lower:
        if any(cue in lower for cue in ("probabilit", "weight", "p(", "p=")):
            from app.modules.math.match.discrete import numeric_data_values

            lists = list(_PROBABILITY_LIST.finditer(cleaned))
            if len(lists) == 2:
                values = numeric_data_values(lists[0].group(1))
                probabilities = numeric_data_values(lists[1].group(1))
                if values is not None and probabilities is not None:
                    return MathIntent(
                        kind="probability",
                        school_op="expected",
                        stats_numbers=values,
                        stats_numbers_b=probabilities,
                        operation="solve",
                    )
            # Retain the probability intent so the model can ask for a valid
            # distribution instead of averaging every number in the sentence.
            return MathIntent(kind="probability", school_op="expected", operation="solve")
        from app.modules.math.match.discrete import numeric_data_values

        nums = numeric_data_values(cleaned[lower.index("expected value") + len("expected value") :])
        if nums is not None:
            return MathIntent(
                kind="probability",
                school_op="expected",
                stats_numbers=nums,
                operation="solve",
            )
    return None


def _verified_block_probability(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if (
        intent.school_op == "dice_conditional_sum"
        and intent.comparator in {"<", "<=", "=", ">=", ">"}
        and intent.combo_n is not None
        and intent.combo_k is not None
    ):
        compare = {
            "<": lambda total: total < intent.combo_n,
            "<=": lambda total: total <= intent.combo_n,
            "=": lambda total: total == intent.combo_n,
            ">=": lambda total: total >= intent.combo_n,
            ">": lambda total: total > intent.combo_n,
        }[intent.comparator]
        sample = [
            (first, second)
            for first in range(1, 7)
            for second in range(1, 7)
            if compare(first + second)
        ]
        favorable = [pair for pair in sample if sum(pair) == intent.combo_k]
        if not sample:
            return None
        probability = Fraction(len(favorable), len(sample))
        comparator_latex = {"<": "<", "<=": r"\le", "=": "=", ">=": r"\ge", ">": ">"}[
            intent.comparator
        ]
        answer = (
            str(probability.numerator)
            if probability.denominator == 1
            else rf"\frac{{{probability.numerator}}}{{{probability.denominator}}}"
        )
        observed_ratio = rf"\frac{{{len(favorable)}}}{{{len(sample)}}}"
        probability_working = (
            observed_ratio if observed_ratio == answer else f"{observed_ratio}={answer}"
        )
        sample_text = "{" + ", ".join(f"({a}, {b})" for a, b in sample) + "}"
        favorable_text = (
            "{" + ", ".join(f"({a}, {b})" for a, b in favorable) + "}" if favorable else "∅"
        )
        lines.extend(
            (
                f"Conditional sample space: {sample_text}",
                f"Favorable outcomes: {favorable_text}",
                f"Probability: {len(favorable)}/{len(sample)} = {probability}",
            )
        )
        direct = (
            "**Conditional sample space**\n\n"
            f"Given $S {comparator_latex} {intent.combo_n}$:\n\n"
            f"${sample_text}$\n\n"
            f"There are **{len(sample)}** equally likely ordered outcomes.\n\n"
            "**Favorable outcomes**\n\n"
            f"For $S = {intent.combo_k}$: ${favorable_text}$\n\n"
            "**Conditional probability**\n\n"
            rf"$P(S={intent.combo_k}\mid S {comparator_latex} {intent.combo_n})="
            f"{probability_working}$" + "\n\n"
            f"```answer\n{answer}\n```\n"
        )
        return replace(_finish_with_answer(lines, answer), direct_reply=direct)
    if (
        intent.school_op == "binomial"
        and intent.combo_n is not None
        and intent.combo_k is not None
        and intent.percent_base is not None
    ):
        answer = math_school.binomial_pmf(intent.combo_n, intent.combo_k, intent.percent_base)
        lines.append(f"P(X={intent.combo_k}) = {answer}")
        return _finish_with_answer(lines, answer)
    if intent.school_op == "expected" and intent.stats_numbers:
        probabilities = intent.stats_numbers_b
        if probabilities is not None:
            if len(probabilities) != len(intent.stats_numbers):
                message = (
                    "Expected value needs one probability for each outcome "
                    f"({len(intent.stats_numbers)} outcomes versus {len(probabilities)} "
                    "probabilities)."
                )
                lines.append(message)
                return VerifiedMathBlock(text="\n".join(lines), direct_reply=message)
            if any(probability < 0 or probability > 1 for probability in probabilities):
                message = "Every probability must be between 0 and 1."
                lines.append(message)
                return VerifiedMathBlock(text="\n".join(lines), direct_reply=message)
            total = sum(probabilities)
            if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-9):
                message = (
                    f"These probabilities sum to {total:g}, not 1, so they do not form "
                    "a valid probability distribution."
                )
                lines.append(message)
                return VerifiedMathBlock(text="\n".join(lines), direct_reply=message)
        answer = math_school.expected_value(intent.stats_numbers, probabilities)
        lines.append(f"E[X] = {answer}")
        return _finish_with_answer(lines, answer)
    from app.modules.math import formulas as math_formulas

    if (
        intent.school_op == "geometric"
        and intent.combo_k is not None
        and intent.percent_base is not None
    ):
        answer = math_formulas.geometric_pmf(intent.combo_k, intent.percent_base)
        lines.append(f"P(X={intent.combo_k}) = {answer}")
        return _finish_with_answer(lines, answer)
    if (
        intent.school_op == "poisson"
        and intent.combo_k is not None
        and intent.percent_base is not None
    ):
        answer = math_formulas.poisson_pmf(intent.combo_k, intent.percent_base)
        lines.append(f"P(X={intent.combo_k}) = {answer}")
        return _finish_with_answer(lines, answer)
    if intent.school_op == "complement" and intent.percent_base is not None:
        answer = math_formulas.complement_probability(intent.percent_base)
        lines.append(f"1-P = {answer}")
        return _finish_with_answer(lines, answer)
    if intent.school_op == "bayes" and intent.vec_a and len(intent.vec_a) == 3:
        prior, hit, false_positive = intent.vec_a
        posterior = math_formulas.bayes_probability(prior, hit, false_positive)
        evidence = hit * prior + false_positive * (1.0 - prior)
        request_text = getattr(intent, "_request_text", "").lower()
        medical = all(name in request_text for name in ("sensitivity", "specificity", "prevalence"))
        if medical:
            answer = f"{float(posterior) * 100:.6g}\\%"
            direct = (
                "**1. Translate the test rates**\n\n"
                f"$P(D)={prior:g}$\n\n"
                f"$P(+\\mid D)={hit:g}$\n\n"
                "Specificity is $P(-\\mid \\neg D)$, so the false-positive rate is\n"
                f"$P(+\\mid \\neg D)=1-{1.0 - false_positive:g}$\n\n"
                f"$P(+\\mid \\neg D)={false_positive:g}$\n\n"
                "**2. Find the total chance of a positive result**\n\n"
                f"$P(+\\cap D)=({hit:g})({prior:g})={hit * prior:g}$\n\n"
                f"$P(+) = ({hit:g})({prior:g}) + ({false_positive:g})(1-{prior:g})$\n\n"
                f"$P(+)={evidence:g}$\n\n"
                "**3. Apply Bayes' theorem**\n\n"
                f"$P(D\\mid +)=\\frac{{({hit:g})({prior:g})}}{{{evidence:g}}}$\n\n"
                f"$P(D\\mid +)={posterior}$\n\n"
                f"$P(D\\mid +)\\approx {answer}$\n\n"
                f"```answer\n{answer}\n```\n"
            )
        else:
            answer = posterior
            direct = (
                "**Bayes' theorem**\n"
                "$P(A\\mid B)=\\frac{P(B\\mid A)P(A)}"
                "{P(B\\mid A)P(A)+P(B\\mid \\neg A)P(\\neg A)}$\n\n"
                "**Substitute**\n"
                f"$P(A\\mid B)=\\frac{{({hit:g})({prior:g})}}"
                f"{{({hit:g})({prior:g})+({false_positive:g})(1-{prior:g})}}={posterior}$\n\n"
                f"```answer\n{answer}\n```\n"
            )
        lines.append(f"P(A|B) = {posterior}")
        return replace(_finish_with_answer(lines, answer), direct_reply=direct)
    return None
