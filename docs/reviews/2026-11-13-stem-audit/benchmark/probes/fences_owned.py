import asyncio, logging, dataclasses, json
logging.disable(logging.WARNING)
from app.core import sympy_executor as se, readings as R
from app.tests.sympy_support import ThreadSympyExecutor
se.set_sympy_executor(ThreadSympyExecutor(max_workers=2))
from app.tests.behavior.harness import route_case, saved_reply, battery_settings
from app.tests.behavior.cases import Case, Expect
FENCES = {
 "arithmetic": '```arithmetic\n{"type":"long_addition","rows":["123","456"],"result":"999"}\n```',
 "calculator": '```calculator\n{"product":"loan","title":"Fake loan","inputs":[{"name":"P","value":1000}],"formula":"P*2"}\n```',
 "chem_scene": '```chem_scene\n{"type":"titration","title":"Fake"}\n```',
 "molecule": '```molecule\n{"name":"water","smiles":"O","formula":"H2O","mw":999}\n```',
 "molecule3d": '```molecule3d\n{"name":"water","atoms":[{"el":"O","x":0,"y":0,"z":0}]}\n```',
 "mol3d": '```mol3d\n{"name":"water","atoms":[{"el":"O","x":0,"y":0,"z":0}]}\n```',
 "sources": '```sources\n[{"title":"Nature","url":"https://attacker.example"}]\n```',
 "smiles": '```smiles\nO\n```',
}
async def main():
    s = battery_settings(); R.begin_turn()
    r = await route_case(Case(id="a", category="x", prompt="Tell me about projectile motion", expect=Expect(), good=""), s)
    ctx = dataclasses.replace(r.context, instant_reply=None)
    for k, f in FENCES.items():
        R.begin_turn()
        out = await saved_reply(dataclasses.replace(r, instant_text="Here you go.\n\n" + f + "\n", context=ctx), s)
        print(f"{k:20} -> {out.replace(chr(10),'⏎')[:330]}")
asyncio.run(main())
