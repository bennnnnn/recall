"""Physics — a subject domain in its own right, not a corner of math.

Physics asks (kinematics, projectile, force, energy) are detected, solved and
rendered by the four modules here:

- ``solver``  — SymPy solves for the unknown and builds trajectory graph specs
- ``extract`` — recognizes a physics ask and produces a ``MathIntent``
- ``direct``  — decides a complete literal ask may show its verified result
- ``block``   — builds the verified system-prompt block for the chat turn

Physics reuses math's shared primitives (``MathIntent``, ``VerifiedMathBlock``,
``MathServiceError``) and plugs into math's dispatch through four registry
seams: ``PHYSICS_EXTRACTORS``, ``PHYSICS_BLOCK_BUILDERS``, ``can_direct_physics``
and ``has_supported_physics_cue``.

This module deliberately imports nothing. ``math_tools.block`` imports
``physics.block`` while it is still initializing, so eagerly pulling the other
physics modules in here would turn that into an import cycle. Import the
submodule you need directly.
"""
