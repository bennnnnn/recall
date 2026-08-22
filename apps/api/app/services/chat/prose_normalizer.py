"""Post-stream prose artifact normalizer.

Cleans up known model output artifacts that survive prompt instructions:
- Orphan colon lines (model puts `:` on its own line as a "leads to next line" marker)
- Excess blank lines (3+ consecutive newlines collapsed to 2)

Runs after all fence enrichment so it never interferes with fence parsing.
Only sets final_content when the text actually changes.
"""

import re

_ORPHAN_COLON_RE = re.compile(r"^[ \t]*:[ \t]*$", re.MULTILINE)
_EXCESS_BLANK_RE = re.compile(r"\n{3,}")


def normalize_prose_artifacts(text: str) -> str:
    """Remove orphan colon lines and collapse excess blank lines.

    Returns the cleaned text. If no artifacts are found, returns the input
    unchanged so callers can skip setting final_content.
    """
    # Remove lines that are solely a colon — the model emits these as a
    # "the formula follows on the next line" marker between a step title
    # and the math. They strand as a lone "two dots" in the rendered output.
    cleaned = _ORPHAN_COLON_RE.sub("", text)

    # Collapse 3+ consecutive newlines to 2 (preserve paragraph breaks,
    # remove excessive gaps left by removed colon lines or model rambling).
    cleaned = _EXCESS_BLANK_RE.sub("\n\n", cleaned)

    # Strip leading/trailing whitespace that may result from removed lines.
    cleaned = cleaned.strip()

    return cleaned


def prose_changed(original: str, normalized: str) -> bool:
    """True when the normalizer actually modified the text."""
    return normalized != original.strip()
