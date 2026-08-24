"""Chat turn orchestration — public stream entrypoints + key types."""

from app.services.chat.verified_output import install_verified_output_contract

# Install before importing the stream facade: stream.py captures math_fence as
# its finalization seam during import. This keeps the transport/client protocol
# backward compatible while making verified output server-owned.
install_verified_output_contract()

from app.services.chat.prompt_builder import StreamStatusFn
from app.services.chat.stream import (
    stream_chat_response,
    stream_edit_response,
    stream_regenerate_response,
)
from app.services.chat.turn_prep import RegenerateBackup, StreamContext

__all__ = [
    "RegenerateBackup",
    "StreamContext",
    "StreamStatusFn",
    "stream_chat_response",
    "stream_edit_response",
    "stream_regenerate_response",
]
