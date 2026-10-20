"""Time the real physics reader on comma runs (REL-01). Run in a subprocess with a timeout."""
import sys, time
sys.path.insert(0, "/home/user/recall-audit/apps/api")
from app.modules.physics.extract import extract_physics_intent, needs_physics
from app.modules.physics.extractors.common import _find_value_with_specific_unit

which = sys.argv[1]
for n in [int(x) for x in sys.argv[2:]]:
    commas = "," * n
    if which == "helper":
        text = f"A body of mass{commas}x 5 kg"
        t = time.perf_counter(); _find_value_with_specific_unit(text, r"kg", ("mass",)); dt = time.perf_counter() - t
    else:
        text = f"What is the net force on a body of mass{commas}x 5 kg accelerating at 2 m/s^2?"
        t = time.perf_counter(); needs = needs_physics(text); intent = extract_physics_intent(text); dt = time.perf_counter() - t
    print(f"{which} n={n}: {dt:.3f} s", flush=True)
