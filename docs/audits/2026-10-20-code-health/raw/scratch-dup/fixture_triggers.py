"""Static check: which calculation-layout branch triggers appear in any shared fixture input (read-only)."""
import json, re, sys
cases = json.load(open("/home/user/recall-audit/docs/fixtures/presentation_cases.json"))["cases"]
inputs = [(c["id"], c["area"], c["input"]) for c in cases]
def hits(pattern, flags=0):
    rx = re.compile(pattern, flags)
    return [cid for cid, _a, text in inputs if rx.search(text)]
checks = {
    r"\begin{ inside maths (split refuses)": r"\\begin\{",
    r"& inside maths (split refuses)": r"\$[^$\n]*&[^$\n]*\$",
    r"\approx in a chain": r"\\approx",
    r"\quad / \qquad break": r"\\q?quad",
    "comma-separated independent equations in one span": r"\$[^$\n]*=[^$\n]*,\s*[^$\n]*=[^$\n]*\$",
    "thousands separator inside maths (1,000)": r"\$[^$\n]*\d,\d{3}[^$\n]*\$",
    r"\Rightarrow / \implies / \to / \iff / \mapsto / arrows (chain stop)": r"\\(?:[Rr]ightarrow|[Ll]eftarrow|to\b|implies|iff|Leftrightarrow|mapsto)",
    "'or' / 'and' between = (chain stop word)": r"=[^=\n$]*\b(?:or|and)\b[^=\n$]*=",
    r"\text / \mathrm units (_TEXT_COMMANDS)": r"\\(?:text|mathrm|mathbf|textrm|operatorname|textbf|mbox)\{",
    r"\times \cdot \div \pm in maths (_NUMERIC_COMMANDS)": r"\\(?:times|cdot|div|pm|mp|cdotp)\b",
    "$$...$$ sole display line": r"(?m)^\s*\$\$[^$]+\$\$[.,;:!?]*\s*$",
    "$...$ sole inline line": r"(?m)^\s*\$[^$]+\$[.,;:!?]*\s*$",
    "plain chain with no $ (a = b = c on its own line)": r"(?m)^(?!.*[$`])[^\n]*=[^\n]*=[^\n]*$",
    "inline code beside maths": r"`[^`]+`[^\n]*\$|\$[^\n]*`[^`]+`",
    "bare number span $2$": r"\$\s*\d[\d,]*(?:\.\d+)?\s*\$",
    "price pair $5 and $10": r"\$\d+(?:\.\d+)?\s+(?:and|or|to)\s+\$\d",
    "list item '- ' / '* ' / '+ ' with maths": r"(?m)^\s*[-*+] .*\$",
    "numbered item '1. ' with maths": r"(?m)^\s*\d{1,3}\. .*\$",
    "table row '|' with chain": r"(?m)^\s*\|.*=.*=",
    "heading '#' with chain": r"(?m)^\s*#.*=.*=",
    r"\( ... \) inline on one line": r"\\\([^\n]*?\\\)",
    r"\( ... \) across lines": r"\\\([^)]*\n[^)]*\\\)",
    r"\( with no closer (live tail)": r"\\\((?![\s\S]*\\\))",
    r"\[ display on one line": r"\\\[[^\n]*\\\]",
    "```math / latex / tex / equation fence": r"(?m)^\s*(?:```|~~~)\s*(?:math|latex|tex|equation)\b",
    "~~~ tilde fence": r"(?m)^\s*~~~",
    "4+ backtick fence": r"(?m)^\s*````",
    "$$ open across lines": r"(?m)^[^$\n]*\$\$[^$\n]*$",
    "indented maths line (sole math, indent kept)": r"(?m)^ {1,3}\$",
    "tab-indented line": r"(?m)^\t",
    "blockquote '>' line with maths": r"(?m)^\s*>.*\$",
    "unit conversion chain (converts_units)": r"=\s*[\d.]+\s*\\(?:text|mathrm)\{\s*\w+\s*\}\s*=\s*[\d.]+\s*\\(?:text|mathrm)",
    "chemistry subscripts (reads_as_prose)": r"[₀₁₂₃₄₅₆₇₈₉⁺⁻]",
    "non-ASCII digits (superscript/Arabic/Ethiopic)": r"[²³¹⁰⁴-⁹٠-٩፩-፱]",
    "non-ASCII letters after backslash": r"\\[^\x00-\x7f]",
    "trailing punctuation after a split span": r"\$[^$\n]*=[^$\n]*=[^$\n]*\$[.,;:!?]",
    "hard break (two trailing spaces)": r"  \n",
}
for name, pat in checks.items():
    found = hits(pat)
    print(f"{len(found):3d}  {name}" + (f"   e.g. {found[:3]}" if found else "   <-- NO FIXTURE INPUT"))
