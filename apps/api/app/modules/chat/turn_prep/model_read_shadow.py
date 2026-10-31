"""The model reader in shadow: it reads the message beside the patterns.

With ``model_reader_shadow_enabled`` on, a turn starts ``turn_reading``'s read of its
message as soon as its subject is read, and the turn's trace line (``turn_trace``) says
whether the model and the patterns read the same law. The read never reaches the reply,
never delays it, and stops when the turn's line is written (docs/MODEL_READER.md).
"""

from __future__ import annotations

import asyncio

from app.core.config import Settings
from app.modules.chat.turn_trace import current_turn_trace
from app.modules.turn_reading.service import read_with_model


def start_model_read_shadow(text: str, settings: Settings) -> None:
    """Start the shadow read of ``text`` for the current turn, once; never raises."""
    if not settings.model_reader_shadow_enabled:
        return
    trace = current_turn_trace()
    if trace is None or trace.emitted or trace.model_read_task is not None:
        return

    async def read() -> None:
        # Bounded on its own: its two calls and the maths read, never longer, whatever the
        # gateway does. Nothing awaits it; the turn's line says ``pending`` meanwhile.
        async with asyncio.timeout(3 * settings.model_reader_timeout_seconds + 1):
            trace.model_read = await read_with_model(text, settings)

    trace.model_read_task = asyncio.create_task(read())
