"""The words that say what a line is about, for the follow-up rules.

``related_questions`` keeps a general follow-up on the user's topic with them, and
``follow_up_thread`` tells a line still on a problem from one that names a topic of its
own. Both read a topic word the same way: four Latin letters or more, accents included,
and not a word every question uses.
"""

from __future__ import annotations

import re

# Lower-case Latin letters with their accents (casefolded text): "pâte" is one word, not
# "p" and "te", and "différence" is not "rence".
LATIN = "a-zß-öø-ÿ\u0100-\u017f"
TOPIC_WORD = re.compile(rf"[{LATIN}]{{4,}}")
STOP_WORDS = frozenset(
    {
        "about",
        "after",
        "again",
        "also",
        "because",
        "been",
        "before",
        "being",
        "best",
        "better",
        "could",
        "does",
        "doing",
        "each",
        "from",
        "have",
        "here",
        "into",
        "just",
        "know",
        "like",
        "make",
        "more",
        "most",
        "much",
        "need",
        "only",
        "other",
        "should",
        "some",
        "than",
        "that",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "thing",
        "things",
        "this",
        "what",
        "when",
        "where",
        "which",
        "while",
        "will",
        "with",
        "would",
        "your",
    }
)
