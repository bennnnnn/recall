"""Request-aware math presentation shared by heuristic and tool-result prompts."""

MATH_REPLY_POLICY = (
    "Math reply policy for this request: Unless the user requested steps, an explanation, "
    "a proof, examples, or hints, give one concise answer with at most the key transformation. "
    "Do not add unsolicited headings, tutorial bullets, sample substitutions, examples, "
    "alternatives, or Note/Tip cards, or repeat the result in equivalent forms. "
    "For an invalid or underspecified problem, state the single reason it cannot be "
    "answered as written, and ask at most one necessary clarification question. "
    "Do not assume missing dimensions or replace the problem with a different example. "
    "If the user requests a derivation, explanation, proof, or examples, provide the "
    "requested reasoning or examples; use only the detail needed. For hints or practice, "
    "give a focused hint without revealing the full solution unless requested. "
    "A deadline or difficulty alone is not a request for a full worked solution. "
    "Honor explicit requests for just the answer or no steps. Always preserve necessary "
    "domains, excluded endpoints or values, all solution branches, units, constants of "
    "integration, and every requested part of the problem."
)
