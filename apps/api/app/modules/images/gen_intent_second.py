"""English "draw me a cat and also explain black holes": a second request after the picture.

The turn's plan cuts it off and answers it beside the picture, so the whole line is not
one picture. Only a request the plan really cuts counts: one with words of its own ("…
and how do magnets work"), not "… and how are you", "… and help", or a clause about the
picture ("… and tell me its name", "… and write Max on its collar").
"""

from __future__ import annotations

from app.services.text_normalize import fold_token

SECOND_ASKS = frozenset({"explain", "tell", "write", "show", "help", "what", "how", "why", "who"})

# "… and tell me its name", "… and show it sleeping": the clause is about the picture.
_POINTS_BACK = frozenset(
    "it its itself them their him his her she he they this that these those".split()
)
# Words that name nothing of their own, so the plan keeps the clause with the picture.
_EMPTY = frozenset(
    "a an the me us you your yours i is are am was were be do does did can could would "
    "will should to of in on at for with and also please pls now so just about up out "
    "going doing today there here".split()
)
_MIN_TOPIC_LETTERS = 3


def asks_separately(parts: list[str]) -> bool:
    """True for "… and (also) explain black holes": a request the plan answers apart."""
    words = [fold_token(part) for part in parts]
    for index, word in enumerate(words[:-1]):
        if word != "and":
            continue
        ask = index + 2 if words[index + 1] == "also" else index + 1
        if ask < len(words) and words[ask] in SECOND_ASKS:
            rest = words[ask + 1 :]
            if any(word in _POINTS_BACK for word in rest):
                return False
            return any(
                len(word) >= _MIN_TOPIC_LETTERS and word not in _EMPTY and word not in SECOND_ASKS
                for word in rest
            )
    return False
