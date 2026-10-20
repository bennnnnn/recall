"""Compare the server's simulation Literal lists with the phone's mirrored arrays (read-only parse)."""
import re
py = open("/home/user/recall-audit/apps/api/app/modules/physics/schemas/simulation.py").read()
ts = open("/home/user/recall-audit/apps/mobile/lib/physics/simulation/parse.ts").read()
spec = open("/home/user/recall-audit/apps/mobile/lib/physics/simulation/spec.ts").read()
def py_literal(name):
    m = re.search(rf"^{name}\s*=\s*Literal\[(.*?)\]", py, re.S | re.M)
    return set(re.findall(r'"([^"]+)"', m.group(1))) if m else None
def ts_array(src, name):
    m = re.search(rf"const {name}[^=]*=\s*\[(.*?)\]", src, re.S)
    return set(re.findall(r'"([^"]+)"', m.group(1))) if m else None
pairs = [("SimulationType", "SCENE_KINDS", ts), ("TitleKey", "SCENE_TITLE_KEYS", spec), ("ArrowKind", "ARROW_KINDS", ts)]
for pyname, tsname, src in pairs:
    a, b = py_literal(pyname), ts_array(src, tsname)
    print(pyname, len(a or ()), "|", tsname, len(b or ()))
    if a is not None and b is not None:
        print("  server-only:", sorted(a - b)); print("  phone-only:", sorted(b - a))
