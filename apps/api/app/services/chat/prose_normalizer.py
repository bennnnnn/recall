"""Post-stream prose artifact normalizer.

Cleans up known model output artifacts that survive prompt instructions:
- Orphan colon lines (model puts `:` on its own line as a "leads to next line" marker)
- Excess blank lines (3+ consecutive newlines collapsed to 2)

Runs after all fence enrichment so it never interferes with fence parsing.
Only sets final_content when the text actually changes.
Never rewrites the inside of fenced code blocks.
"""

from __future__ import annotations


def normalize_prose_artifacts(text: str) -> str:
    """Remove orphan colon lines and collapse excess blank lines outside fences."""
    lines = text.split("\n")
    out: list[str] = []
    in_fence = False
    blank_run = 0
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            blank_run = 0
            out.append(line)
            continue
        if in_fence:
            out.append(line)
            continue
        if stripped == ":":
            blank_run += 1
            if blank_run < 2:
                out.append("")
            continue
        if stripped == "":
            blank_run += 1
            if blank_run >= 2:
                continue
            out.append(line)
            continue
        blank_run = 0
        out.append(line)
    return "\n".join(out).strip()


def prose_changed(original: str, normalized: str) -> bool:
    """True when the normalizer actually modified the text."""
    return normalized != original.strip()
