"""Run the review's 50 physics questions through the real offline chat path.

    cd apps/api && uv run python ../../docs/reviews/2026-11-12-physics/run_questions.py /tmp/out.json

Uses the STEM sweep's judge (``app/tests/behavior/stem_sweep.py``): model calls are stubbed,
so a turn the server cannot verify shows no reply text, only what the model would be given.
"""

import asyncio
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

from app.core.sympy_executor import set_sympy_executor
from app.tests.behavior import stem_sweep as sw
from app.tests.sympy_support import ThreadSympyExecutor

HERE = Path(__file__).resolve().parent
OUT = Path(sys.argv[1])
set_sympy_executor(ThreadSympyExecutor(max_workers=1))


async def main() -> None:
    corpus = Path(tempfile.mkdtemp())
    (corpus / "physics").mkdir()
    shutil.copy(HERE / "questions.json", corpus / "physics" / "questions.json")
    sw.CORPUS = corpus
    entries = sw.load("physics")
    outs, rows = [], []
    for entry in entries:
        start = time.perf_counter()
        try:
            outcome = await sw.run_entry(entry, "physics")
        except Exception as exc:  # A crash is a finding.
            outcome = sw.Outcome(entry=entry, problems=[sw.Problem("misread", repr(exc))])
        route = outcome.route
        outs.append(outcome)
        rows.append(
            {
                "id": entry.id,
                "prompt": entry.prompt,
                "expect": entry.expect,
                "visual_wanted": entry.visual,
                "seconds": round(time.perf_counter() - start, 3),
                "subject": route.subject if route else None,
                "solved": route.solved if route else None,
                "instant": route.instant if route else None,
                "model": route.model if route else None,
                "got": outcome.got,
                "visuals": outcome.visuals,
                "problems": [[p.kind, p.text] for p in outcome.problems],
                "reply": outcome.reply,
                "server_pictures": route.server_pictures if route else "",
                "verified_answer": route.verified_answer if route else "",
                "verified_text": route.verified_text if route else "",
                "system_prompt_chars": len(route.system_prompt) if route else 0,
            }
        )
    OUT.write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    print(sw.report(outs, show=True))


asyncio.run(main())
