"""For each API route, does a client (mobile or web, non-test source) name its path?

Usage: python -I route_clients.py routes.txt /home/user/recall-audit
"""

from __future__ import annotations

import os
import re
import sys

routes = [line.rstrip("\n").split("\t") for line in open(sys.argv[1]) if line.strip()]
REPO = sys.argv[2]


def sources(base: str) -> dict[str, str]:
    out = {}
    for dirpath, dirs, fs in os.walk(base):
        dirs[:] = [d for d in dirs if d not in ("node_modules", "__tests__", "vendor", ".expo", "dist", "ios", "android")]
        for f in fs:
            if f.endswith((".ts", ".tsx", ".js", ".mjs", ".cjs")) and ".test." not in f:
                p = os.path.join(dirpath, f)
                try:
                    out[p] = open(p, encoding="utf-8").read()
                except (OSError, UnicodeDecodeError):
                    pass
    return out


mobile = sources(os.path.join(REPO, "apps/mobile"))
web = sources(os.path.join(REPO, "apps/web"))
scripts = {}
for base in ("scripts",):
    for dirpath, _d, fs in os.walk(os.path.join(REPO, base)):
        for f in fs:
            p = os.path.join(dirpath, f)
            try:
                scripts[p] = open(p, encoding="utf-8").read()
            except (OSError, UnicodeDecodeError):
                pass


def pattern(path: str) -> re.Pattern[str]:
    parts = []
    for seg in path.strip("/").split("/"):
        if seg.startswith("{"):
            parts.append(r"(?:\$\{[^}]+\}|[^/\s'\"`]+)")
        else:
            parts.append(re.escape(seg))
    body = r"/".join(parts)
    # allow a trailing query string, quote or template end
    return re.compile(r"[`'\"]/" + body + r"(?:[`'\"?]|$|\$\{)", re.M)


for method, path, loc, handler in routes:
    pat = pattern(path)
    m_hits = [os.path.relpath(p, REPO) for p, s in mobile.items() if pat.search(s)]
    w_hits = [os.path.relpath(p, REPO) for p, s in web.items() if pat.search(s)]
    s_hits = [os.path.relpath(p, REPO) for p, s in scripts.items() if path.split("{")[0].rstrip("/") in s]
    status = "MOBILE" if m_hits else ("WEB" if w_hits else ("SCRIPT" if s_hits else "NONE"))
    print(f"{status}\t{method}\t{path}\t{loc}\t{handler}\tmobile={m_hits[:2]}\tweb={w_hits[:1]}")
