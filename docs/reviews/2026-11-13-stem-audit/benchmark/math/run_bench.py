"""Run the audit's maths questions through the offline chat path (models stubbed).
cd apps/api && uv run python <this> <questions.py dir> <out.json>"""
import asyncio, json, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from questions import Q
from app.core.sympy_executor import set_sympy_executor
from app.tests.behavior import stem_sweep as sw
from app.tests.behavior.stem_math_judge import pieces, close
from app.tests.sympy_support import ThreadSympyExecutor
from sympy import sympify
OUT = Path(sys.argv[2])
set_sympy_executor(ThreadSympyExecutor(max_workers=1))
ONLY = set(sys.argv[3].split(",")) if len(sys.argv) > 3 else None

async def main():
    corpus = Path(tempfile.mkdtemp()); (corpus / "math").mkdir()
    qs = [q for q in Q if not ONLY or q["id"] in ONLY]
    raw = [{k: v for k, v in q.items() if k in ("id","area","prompt","expect","check","locale","history")} for q in qs]
    (corpus / "math" / "q.json").write_text(json.dumps(raw))
    sw.CORPUS = corpus
    entries = sw.load("math"); byid = {q["id"]: q for q in qs}
    rows, outs = [], []
    for entry in entries:
        t = time.perf_counter()
        try:
            o = await sw.run_entry(entry, "math")
        except Exception as exc:
            o = sw.Outcome(entry=entry, problems=[sw.Problem("misread", "CRASH " + repr(exc))])
        dt = time.perf_counter() - t
        r = o.route; q = byid[entry.id]
        card = ""
        if r is not None:
            card = sw.answer_card(o.reply) if o.reply else (r.verified_answer or "")
        forbidden = []
        for f in q.get("forbid", []):
            try:
                if any(close(v, sympify(f)) for v in pieces(card)): forbidden.append(f)
            except Exception: pass
        tr = r.trace if r else None
        rows.append(dict(id=entry.id, area=entry.area, tag=q.get("tag"), prompt=entry.prompt, expect=entry.expect,
            check=q.get("check"), seconds=round(dt, 3),
            subject=r.subject if r else None, solved=r.solved if r else None, instant=r.instant if r else None,
            model=r.model if r else None, search=r.search if r else None,
            card=card, forbidden_on_card=forbidden,
            problems=[[p.kind, p.text] for p in o.problems],
            reply=o.reply[:3000], verified_answer=r.verified_answer if r else "", verified_text=(r.verified_text or "")[:1500] if r else "",
            system_tail=(r.system_prompt[-2500:] if r else ""),
            hints=sorted(r.hints) if r else [],
            trace=(tr.as_dict() if hasattr(tr, "as_dict") else repr(tr)[:1500]) if tr else None))
        print(entry.id, f"{dt:.2f}s", rows[-1]["subject"], "solved" if rows[-1]["solved"] else "-", [p.kind for p in o.problems], flush=True)
        outs.append(o)
    OUT.write_text(json.dumps(rows, indent=1, ensure_ascii=False, default=str))
    print(sw.report(outs, show=False))
asyncio.run(main())
