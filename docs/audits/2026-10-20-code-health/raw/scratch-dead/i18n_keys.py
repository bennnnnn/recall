"""i18n keys in en.json that no production source names, literally or by a dynamic prefix.

A key counts as used when its full dotted name appears in a string in non-test source, or when a
template/concatenation builds keys from a prefix that the key starts with (for example
t(`drawer.${key}`) uses every drawer.* key... only one level deep after the prefix).
Plural suffixes (_one, _other, _zero, _few, _many, _two) are folded into their base key.

Usage: python -I i18n_keys.py /home/user/recall-audit/apps/mobile
"""

from __future__ import annotations

import json
import os
import re
import sys

ROOT = sys.argv[1]
en = json.load(open(os.path.join(ROOT, "lib/i18n/en.json"), encoding="utf-8"))


def flatten(d, prefix=""):
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            yield from flatten(v, key)
        else:
            yield key


keys = list(flatten(en))
PLURAL = re.compile(r"_(one|other|zero|few|many|two)$")
base_keys = sorted({PLURAL.sub("", k) for k in keys})

texts = []
for d in ("app", "components", "features", "lib", "hooks", "contexts", "ui"):
    for dirpath, dirs, fs in os.walk(os.path.join(ROOT, d)):
        dirs[:] = [x for x in dirs if x not in ("__tests__", "vendor", "i18n")]
        for f in fs:
            if f.endswith((".ts", ".tsx")) and ".test." not in f:
                texts.append(open(os.path.join(dirpath, f), encoding="utf-8").read())
blob = "\n".join(texts)
strings = set(re.findall(r"[\"'`]([A-Za-z0-9_.\-]+)[\"'`]", blob))
# dynamic prefixes: `prefix.${...}` or "prefix." + ...
dyn = set(re.findall(r"`([A-Za-z0-9_.]+\.)\$\{", blob)) | set(re.findall(r"[\"']([A-Za-z0-9_.]+\.)[\"']\s*\+", blob))
# partial suffix templates like `chat.status.${phase}_1`
dyn_mid = re.findall(r"`([A-Za-z0-9_.]*)\$\{[^}]+\}([A-Za-z0-9_.]*)`", blob)

unused = []
for k in base_keys:
    if k in strings:
        continue
    if any(k.startswith(p) for p in dyn):
        continue
    if any(k.startswith(a) and k.endswith(b) and (a or b) for a, b in dyn_mid):
        continue
    unused.append(k)
print(f"# keys={len(keys)} base={len(base_keys)} unused={len(unused)}")
for k in unused:
    print(k)
