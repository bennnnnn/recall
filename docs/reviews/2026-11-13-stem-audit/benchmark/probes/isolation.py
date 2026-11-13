"""One subject raising: does it take down other subjects' turns? (thread executor so patches reach the pool)."""
import asyncio, logging, sys
logging.basicConfig(level=logging.ERROR, format="%(levelname)s %(name)s: %(message)s")
from unittest.mock import patch
from app.core import sympy_executor as se, readings as R
from app.tests.sympy_support import ThreadSympyExecutor
se.set_sympy_executor(ThreadSympyExecutor(max_workers=2))
from app.tests.behavior.harness import route_case, saved_reply, battery_settings
from app.tests.behavior.cases import Case, Expect
from app.modules.chemistry.subject import ChemistrySubject, ChemistryFollowups
from app.modules.physics.subject import PHYSICS_SUBJECT
def boom(*a, **k): raise RuntimeError("injected chemistry bug")
async def aboom(*a, **k): raise RuntimeError("injected chemistry bug")
PROMPTS = ["Solve 2x + 5 = 17", "A car accelerates from 0 to 30 m/s in 6 s. What is its acceleration?", "What is the molar mass of H2SO4?", "hi there"]
INJECT = {
  "chem.solve raises": ("app.modules.chemistry.subject.ChemistrySubject.solve", aboom),
  "chem.followups.continues_alone raises": ("app.modules.chemistry.subject.ChemistryFollowups.continues_alone", boom),
  "chem.asks raises": ("app.modules.chemistry.subject.ChemistrySubject.asks", boom),
  "chem.fast_lane raises": ("app.modules.chemistry.subject.ChemistrySubject.fast_lane", boom),
  "chem is_chemistry_question raises (order.py)": ("app.modules.chemistry.request.is_chemistry_question", boom),
  "chem.fence.owns raises": ("app.modules.chemistry.subject.ChemistryFence.owns" , boom),
}
async def main():
    s = battery_settings()
    for label, (target, fn) in INJECT.items():
        res = []
        try:
            p = patch(target, fn); p.start()
        except Exception as e:
            print(label, "PATCH FAILED", e); continue
        for prompt in PROMPTS:
            R.begin_turn()
            try:
                r = await route_case(Case(id="a", category="x", prompt=prompt, expect=Expect(), good=""), s)
                if r.instant_text:
                    await saved_reply(r, s)
                res.append(f"{prompt[:14]}: {r.subject or '-'}{'+solved' if r.solved else ''}")
            except Exception as e:
                res.append(f"{prompt[:14]}: CRASH {type(e).__name__}")
        p.stop()
        print(f"{label:45} | " + " | ".join(res), flush=True)
asyncio.run(main())
