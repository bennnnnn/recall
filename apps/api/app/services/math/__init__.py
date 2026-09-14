"""Math — the symbolic pipeline, from raw user text to a verified answer.

Three stages, each its own subpackage:

- ``match``  — cheap text scanning: does this look like math, and what kind
- ``tools``  — intent extraction, direct-reply decisions, verified block and
               prompt augmentation (the stage that decides what to hand the model)
- ``solve``  — SymPy evaluation: actually compute the answer

Alongside them: ``fence`` (post-stream fence correction), ``school``,
``followup``, ``ocr`` / ``image_extract`` (math from photos), ``reply_policy``
and ``sympy_executor`` (the sandboxed SymPy process pool).

Physics is a peer subject, not a corner of this package — see
``app.services.physics``.

Imports nothing on purpose: ``tools.block`` and ``physics.block`` reference
each other's primitives during initialization, so eager re-exports here would
close an import cycle. Import the submodule you need directly.
"""
