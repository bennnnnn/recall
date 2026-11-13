"""Confirming checks for the P0 findings (expected to FAIL on today's code).

cd apps/api && uv run python <this file>
"""
import math
from app.modules.chemistry.extract import extract_chemistry_intent
from app.modules.chemistry.block import build_verified_chemistry
from app.modules.physics.extract import extract_physics_intent

fails = 0
def check(name, ok, detail):
    global fails
    fails += not ok
    print(("PASS " if ok else "FAIL ") + name + " :: " + detail)

# CHEM-01: "75% ... decay/decompose" is read as 75% remaining.
for prompt in ("How long will it take for 75% of a radioactive sample to decay if its half-life is 10 years?",
               "How long does it take for 75% of a first-order reactant to decompose if its half-life is 12 min?"):
    it = extract_physics_intent(prompt)
    left = (it.physics_params or {}).get("fraction_left") if it else None
    check("CHEM-01 fraction decayed is not fraction left", left in (None, 25.0), f"{prompt!r} -> fraction_left={left}")

# CHEM-02: an unlabelled "at 350 K" in a Nernst question is replaced by 298.15 K.
it = extract_chemistry_intent("E° = 0.80 V, n = 1, Q = 0.010 at 350 K. Use the Nernst equation to find E.")
T = it.params.get("temperature") if it else None
check("CHEM-02 Nernst keeps the stated temperature", it is None or abs(T - 350) < 1e-6, f"temperature={T}")
if it:
    v = build_verified_chemistry(it)
    print("   answer:", v.result.answer, "| correct at 350 K:", round(0.80 - 8.314462618*350/96485.33212*math.log(0.01), 4))
print("failures:", fails)
