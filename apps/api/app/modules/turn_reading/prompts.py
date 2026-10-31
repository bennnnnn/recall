"""The two prompts the model reader sends, built from the subjects' own catalogs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.services.law_binding.model_read import OpCard

# Each kind is shown with the first results its laws find, so the model can place it.
_FINDS_PER_KIND = 5

_ROUTE = """Classify a student's question. It may be in any language.

Return JSON only: {{"subject": "physics" | "chemistry" | "math" | "none", "kind": <one kind
listed for that subject, or null>}}.

- physics or chemistry: a question that asks for a number one law gives from values the
  question states. Pick the kind whose results match what is asked.
- math: an equation, expression, calculus, geometry, statistics or probability question.
- none: anything else, including explanations, opinions and everyday chat.

Physics kinds:
{physics}

Chemistry kinds:
{chemistry}"""

_LAW = """Read a student's {subject} question (in any language) into ONE law from the list
below and the values the question states.

Laws (id: what it finds; its inputs as name (symbol, SI unit)):
{laws}

Return JSON only:
{{"op": "<law id, or none when no law answers the whole question>",
  "givens": [{{"name": "<an input name of that law>", "value": <the number as written,
  as a plain decimal>, "unit": "<its unit as an SI symbol: m, s, kg, m/s, m/s^2, N, J,
  W, Pa, K, degC, mol, L, mol/L, g, kJ, kJ/mol, …; empty for a pure number; deg for an
  angle in degrees>", "quote": "<the question's exact characters that state this value,
  copied verbatim in the question's own language and digits>"}}],
  "unused": ["<exact quote of each other number the question writes>"],
  "formula": "<the chemical formula the law is about, or null>"}}

Rules:
- Copy, never compute: a value is a given only when the question writes it. Do not
  convert units, add constants (g, the speed of light) or fill in missing values.
- Every number the question writes appears in exactly one given's quote or in unused.
- If no law on the list answers what is asked, return {{"op": "none"}}."""


def _kinds(menu: Mapping[str, Sequence[OpCard]]) -> str:
    return "\n".join(
        f"- {kind}: " + "; ".join(card.finds for card in cards[:_FINDS_PER_KIND])
        for kind, cards in sorted(menu.items())
    )


def route_prompt(
    physics: Mapping[str, Sequence[OpCard]], chemistry: Mapping[str, Sequence[OpCard]]
) -> str:
    return _ROUTE.format(physics=_kinds(physics), chemistry=_kinds(chemistry))


def law_prompt(subject: str, cards: Sequence[OpCard]) -> str:
    return _LAW.format(subject=subject, laws="\n".join(card.line() for card in cards))
