"""SymPy pool workers must stay small: no model client, no web or DB stack.

Each API process runs ``sympy_max_workers`` (3) spawned workers, each its own
Python process. The math package once imported the LiteLLM gateway at module
top, which put litellm, openai and tiktoken into every worker: about 237 MB per
worker after the warm-up solve instead of about 86 MB.
"""

from __future__ import annotations

import subprocess
import sys

from app.tests.architecture.boundary_support import APP_ROOT

# What every function handed to ``run_sympy`` imports in the worker.
_WORKER_IMPORTS = (
    "from app.modules.math.sympy_warmup import warm_math_worker",
    "warm_math_worker()",
    "import app.modules.math.tools.block",
    "import app.modules.math.fence",
    "import app.modules.physics.prompt",
    "import app.modules.chemistry.fence",
)
_HEAVY = ("litellm", "openai", "tiktoken", "sqlalchemy", "fastapi")


def test_sympy_worker_does_not_import_the_model_client_or_web_stack() -> None:
    script = "\n".join(
        [
            "import sys",
            *_WORKER_IMPORTS,
            f"print(','.join(m for m in {_HEAVY!r} if m in sys.modules))",
        ]
    )
    result = subprocess.run(  # noqa: S603 - fixed argv: this interpreter and literal imports
        [sys.executable, "-c", script],
        cwd=APP_ROOT.parent,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    loaded = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
    assert loaded == "", f"SymPy worker imports pulled in: {loaded}"
