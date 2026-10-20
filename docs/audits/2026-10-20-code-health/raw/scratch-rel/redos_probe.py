"""Time two backend regexes against crafted gaps (local regex micro-benchmark only)."""
import re
import sys
import time

LABEL_GAP = re.compile(
    r"(?:[\s,:=.]+|(?:of|is|are|was|were|a|an|the|height|distance|equal|to)\b)*",
    re.IGNORECASE,
)
UNIT_TAIL = re.compile(r"(?:[A-Za-zµμΩ°%]+(?:\^-?\d+)?|[/·*]|\s|[()])*")

which = sys.argv[1]
n = int(sys.argv[2])
if which == "gap":
    s = "," * n + "x"
    t = time.perf_counter(); r = LABEL_GAP.fullmatch(s); dt = time.perf_counter() - t
elif which == "gapsp":
    s = " " * n + "x"
    t = time.perf_counter(); r = LABEL_GAP.fullmatch(s); dt = time.perf_counter() - t
elif which == "unit":
    s = "m" * n + "!"
    t = time.perf_counter(); r = UNIT_TAIL.fullmatch(s); dt = time.perf_counter() - t
print(which, n, bool(r), f"{dt:.4f}s")
