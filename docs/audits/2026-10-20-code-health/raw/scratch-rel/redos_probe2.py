"""Time finalize-pass regexes (copied verbatim) on long adversarial replies. Regex-only probe."""
import re, sys, time
_CLAIM_VERB = r"(?:verified|checked|confirmed|double[- ]checked)"
_CHECKER = (
    r"(?:sympy|sym\s*py|the\s+(?:symbolic\s+)?solver|a\s+(?:symbolic\s+)?solver|"
    r"the\s+(?:symbolic\s+|math\s+)+engine|a\s+(?:symbolic\s+)?(?:math\s+)?engine|"
    r"symbolic\s+(?:math|algebra)|a\s+computer\s+algebra\s+system|a\s+cas|"
    r"the\s+cas|the\s+server|the\s+app)"
)
SENTENCE = re.compile(
    rf"(?:(?<=^)|(?<=[.!?\n])[ \t]*)[^.!?\n]*\b{_CLAIM_VERB}[ \t]+(?:with|by|using|via|in)[ \t]+"
    rf"{_CHECKER}\b[^.!?\n]*[.!]?",
    re.IGNORECASE,
)
TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
which, n = sys.argv[1], int(sys.argv[2])
if which == "sentence":
    s = "word " * n          # one long sentence with no . ! ? or newline
    t = time.perf_counter(); r = SENTENCE.sub("", s); dt = time.perf_counter() - t
elif which == "sentence2":
    s = ("verified " * n)
    t = time.perf_counter(); r = SENTENCE.sub("", s); dt = time.perf_counter() - t
elif which == "table":
    s = " " * n + "x"
    t = time.perf_counter(); r = TABLE_RULE.match(s); dt = time.perf_counter() - t
print(which, n, f"{dt:.4f}s")
