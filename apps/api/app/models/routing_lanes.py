"""The aliases routing picks by job: data, changed here and not in routing code.

``app.models.model_catalog`` serves Auto's, the photo and the tool lanes
(``auto_fast_alias``, ``vision_alias``, ``tool_selector_aliases``, ...); a background
job reads its own lane (``ROUTING.background``). ``test_model_catalog`` checks each lane
against the capability its job needs, so a lane can't point at a model that can't do it.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class RoutingLanes:
    """One product alias per job (Auto's three lanes, photos, tools, background calls)."""

    # Qwen3.7 Flash answers an everyday turn as fast as GPT-6 Luna (about 0.8s to
    # first text with thinking off) for about a third of the price. Auto's
    # everyday lane carries most turns; hard and maths turns route stronger.
    everyday: str
    # Auto's everyday lane on a plan that includes the stronger one (Pro:
    # ``entitlements.has_strong_everyday_model``). A 60-turn live chat on Qwen3.7 Flash
    # (2026-10-25) named the wrong author for a book, called a 2026 TV season
    # unaired, told the user they had a game result wrong against its own sources,
    # and wrote a web_search fence as text instead of searching. Claude Haiku 5.5
    # answers everyday turns carefully at a few times Qwen's price per token.
    everyday_strong: str
    hard: str
    # Maths, physics and chemistry no solver verified, written as a ```worked block. GLM 5.2
    # held the block on the harness's prompt but answered the owner's "How many solutions
    # does $4X^2 + 4 = 6$ have?" with no working (2026-11-10), at four times DeepSeek's cost
    # a turn; DeepSeek kept the block on 100% of 17 unverified questions at 0.4 s to the
    # first word with thinking off and 1.9 s at low (``math_lane_eval``). Its thinking
    # follows the turn's read, question by question. A plan without it (Free) gets its
    # pool's strongest model of the tier (GLM 5.3 Flash).
    math: str
    # A turn that shows the model a photo, when its own model cannot read one,
    # and the second photo reader (another company) when the first fails.
    vision: str
    vision_backup: str
    # The tool-selection round, in order: one fast tool-capable model, then one
    # from another company when the first fails.
    tool_selectors: tuple[str, ...]
    # A background structured call (memory, titles, word problems) asks this once when
    # its own model fails or answers out of shape. It must do JSON mode.
    structured_fallback: str
    # Background jobs: memory's facts and sections, a chat's summary, the follow-up
    # questions under a reply, and which earlier chat a message means. JSON mode.
    background: str
    # A new chat's title.
    titles: str
    # A word problem turned into equations, and the maths read when the rules find none.
    # Both run before the reply's first text, so a fast model; its output is only a
    # candidate (number grounding and SymPy check it). JSON mode.
    word_problems: str
    math_extract: str
    # How to handle a message (``chat.turn_decision``): live facts, subject, effort, picture
    # and follow-up. The reply waits on it, so the fastest JSON-mode model (Qwen3.7 Flash
    # read 8 of 8 search questions right in about 0.7s; GPT-6 Luna took over 2s).
    live_read: str
    # The read again when its model refuses at once (an upstream rate limit, 15-40% of calls
    # at busy hours on 2026-11-10), inside the same wait. Claude Haiku 5.5 read the decider
    # corpus with the lane's subject on 94% and the effort on 94%, p95 0.82 s; Qwen3.7 Flash
    # and GPT-6 Luna both failed on 8-16% of calls in the same hour.
    live_read_backup: str
    # How to handle a message, answered as probabilities (``chat.decider_read``): subject,
    # effort, picture, follow-up, live facts. The text read above writes the search query and
    # answers when it fails.
    decider: str
    # Which earlier message "draw it" or "show it" means (``chat.referent_read``): the turn
    # waits on it, so the same fast JSON-mode model.
    referent_read: str
    # Auto's lane for a turn the read decided, by its subject: the lane for effort none, low
    # and high, one of "everyday", "hard" and "math" above. Data, so routing names no model.
    # A subject not here (money: its calculator card holds the numbers) keeps the word
    # rules' lane. Only a hard question goes to the strong lane on a plan that has it (the
    # owner's call, 2026-11-10): a low one, code too, stays on the everyday lane and thinks
    # there (a git how-to read as low code waited 7.8 s on DeepSeek). STEM nothing verified
    # goes to the maths lane.
    decided: Mapping[str, tuple[str, str, str]]


ROUTING = RoutingLanes(
    everyday="qwen-3.7-flash",
    everyday_strong="free-chat",
    hard="smart-chat",
    math="smart-chat",
    vision="vision-chat",
    vision_backup="fallback-vision-model",
    tool_selectors=("gpt-6-luna", "free-chat"),
    structured_fallback="fallback-memory-model",
    background="memory-model",
    titles="title-model",
    word_problems="gpt-6-luna",
    math_extract="gpt-6-luna",
    live_read="title-model",
    live_read_backup="free-chat",
    decider="decider-model",
    referent_read="title-model",
    decided=MappingProxyType(
        {
            "everyday": ("everyday", "everyday", "hard"),
            "code": ("everyday", "everyday", "hard"),
            "maths": ("math", "math", "hard"),
            "physics": ("math", "math", "hard"),
            "chemistry": ("math", "math", "hard"),
        }
    ),
)
