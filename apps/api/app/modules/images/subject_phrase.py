"""What an image request asks for: the first noun phrase of its subject.

"An image of a robot arm holding a test tube" is a robot arm; the test tube is in the
scene. The written-thing check (``gen_intent.has_non_image_subject``) reads this phrase
only, so a word for something written later in the scene no longer turns a picture away.
"""

from __future__ import annotations

from app.modules.images.gen_intent_words import ARTICLES, POSSESSIVES
from app.services.text_normalize import fold_token

MARKUP_WORDS = frozenset({"html", "css", "javascript", "typescript"})


# Where the thing asked for ends and the scene around it begins.
SCENE_WORDS = frozenset(
    {
        "with",
        "on",
        "in",
        "at",
        "by",
        "from",
        "near",
        "under",
        "over",
        "beside",
        "behind",
        "above",
        "below",
        "inside",
        "and",
        "while",
        "that",
        "which",
        "who",
    }
)


def first_phrase(raw_words: list[str]) -> list[str]:
    """The subject's first noun phrase, the thing the picture is of: what follows a
    preposition, a comma or an "-ing" verb with an object describes it (all of it counts
    when it names markup, "a logo for my website in html"). "A robot arm holding a test tube"
    is a robot arm, not a test; "tips for studying" and "a meeting summary" stay written."""
    folded = [fold_token(raw) for raw in raw_words]
    if any(word in MARKUP_WORDS for word in folded):
        return folded
    words: list[str] = []
    for i, (raw, word) in enumerate(zip(raw_words, folded, strict=True)):
        named = any(kept not in ARTICLES and kept not in POSSESSIVES for kept in words)
        nxt = folded[i + 1] if i + 1 < len(folded) else ""
        # "-ing" with an object is a verb: "holding a", "wearing her" (not "an opening line").
        acts = word.endswith("ing") and (nxt in ARTICLES or nxt in POSSESSIVES)
        if named and (word in SCENE_WORDS or acts):
            break
        words.append(word)
        if raw.endswith(","):
            break
    return words
