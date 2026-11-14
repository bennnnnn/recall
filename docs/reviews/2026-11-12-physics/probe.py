import asyncio, sys, json
from app.tests.behavior import stem_sweep as sw
from app.core.sympy_executor import set_sympy_executor
from app.tests.sympy_support import ThreadSympyExecutor
set_sympy_executor(ThreadSympyExecutor(max_workers=1))
probes = json.load(open(sys.argv[1]))
async def main():
    for group, items in probes.items():
        print("##", group)
        for p in items:
            e = sw.Entry(id="p", area="x", prompt=p, expect="answer")
            o = await sw.run_entry(e, "physics")
            r = o.route
            card = sw.answer_card(o.reply) if o.reply else (r.verified_answer if r else "")
            print(f"  solved={r.solved!s:<5} subj={r.subject or '-':<9} pics={','.join(sw.check_visuals(o.reply or r.server_pictures)[0]) or '-':<20} card={' '.join(card.split())[:45]!s:<45} | {p}")
asyncio.run(main())
