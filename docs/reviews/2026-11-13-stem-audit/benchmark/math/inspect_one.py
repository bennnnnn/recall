import asyncio, sys, re
from app.core.sympy_executor import set_sympy_executor
from app.tests.sympy_support import ThreadSympyExecutor
from app.tests.behavior.harness import Case, Expect, route_case
set_sympy_executor(ThreadSympyExecutor(max_workers=1))
async def main():
    locale = "en"
    for prompt in sys.argv[1:]:
        if prompt.startswith("locale="): locale = prompt[7:]; continue
        r = await route_case(Case("x", "x", prompt, Expect(), "", locale=locale))
        print("=====", repr(prompt), "subject=", r.subject, "solved=", r.solved, "instant=", r.instant, "model=", r.model, "search=", r.search)
        print("VERIFIED_ANSWER:", repr(r.verified_answer[:300]))
        sp = r.system_prompt
        # print math-specific paragraphs
        for para in sp.split("\n\n"):
            if re.search(r"(?i)math note|verified|sympy|solver|not.*verif|worked|lcm|part", para) and len(para) < 3000:
                print("  >>", para[:700].replace("\n", " | "))
        if r.instant_text: print("INSTANT:", r.instant_text[:600])
asyncio.run(main())
