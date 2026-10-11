"""Strip inline think fences from a streamed reply."""

from __future__ import annotations

# DeepSeek-R1 (and similar) emit inline think fences in `content`, plus a
# separate `reasoning_content` delta. Hex-encode the tags so a source rewrite
# cannot turn this filter into a no-op. Strip the fences from tokens; do not
# forward `reasoning_content` to the client (the chat UI must not show CoT).
THINK_OPEN = "\x3cthink\x3e"
THINK_CLOSE = "\x3c/think\x3e"
# Hold an unclosed think block this long while streaming. R1 CoT on even a
# short ask is often >4k chars; giving up early leaked the rest into the bubble.
THINK_MAX_OPEN_BUFFER = 65_536


class ThinkStripper:
    """Stateful filter that removes inline think fences from a token stream.

    Handles open/close tags split across chunks. Emits text outside think blocks
    unchanged; discards text inside. An unclosed think block is dropped on flush.
    """

    def __init__(self) -> None:
        self._buf = ""
        self._in_think = False

    def feed(self, chunk: str) -> str:
        self._buf += chunk
        out: list[str] = []
        while True:
            if self._in_think:
                idx = self._buf.find(THINK_CLOSE)
                if idx == -1:
                    if len(self._buf) > THINK_MAX_OPEN_BUFFER:
                        # Model forgot to close — give up on this block.
                        self._buf = ""
                        self._in_think = False
                    break
                self._buf = self._buf[idx + len(THINK_CLOSE) :]
                self._in_think = False
            else:
                idx = self._buf.find(THINK_OPEN)
                if idx == -1:
                    # Hold back enough trailing chars that a split open tag can't leak.
                    safe = len(self._buf) - (len(THINK_OPEN) - 1)
                    if safe > 0:
                        out.append(self._buf[:safe])
                        self._buf = self._buf[safe:]
                    break
                out.append(self._buf[:idx])
                self._buf = self._buf[idx + len(THINK_OPEN) :]
                self._in_think = True
        return "".join(out)

    def flush(self) -> str:
        if self._in_think:
            self._buf = ""
            self._in_think = False
            return ""
        out = self._buf
        self._buf = ""
        return out
