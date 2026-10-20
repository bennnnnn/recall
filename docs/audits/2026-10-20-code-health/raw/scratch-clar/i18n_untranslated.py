"""Count non-English locale values (3+ words) identical to en.json. Read-only."""
import json, glob, os
D = "/home/user/recall-audit/apps/mobile/lib/i18n"
def flat(d, p=""):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict): out.update(flat(v, p + k + "."))
        else: out[p + k] = v
    return out
en = flat(json.load(open(os.path.join(D, "en.json"))))
for f in sorted(glob.glob(os.path.join(D, "*.json"))):
    if f.endswith("en.json"): continue
    d = flat(json.load(open(f)))
    same = [k for k, v in d.items() if k in en and v == en[k] and isinstance(v, str) and len(v.split()) >= 3]
    print(os.path.basename(f), len(d), "identical-to-en (3+ words):", len(same))
