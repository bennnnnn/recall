"""English "draw me a cat and also explain black holes": a second request after the picture.

The turn's plan cuts it off and answers it beside the picture, so the whole line is not
one picture. Only a cut the plan really makes counts, read with the plan's own rules
(``services/request_words``): "… and also <request>" always; "… and <request>" when the
request names something of its own the picture does not ("… and tell me a joke"). "…
and tell me about dog breeds" after a dog, "… and show the cat sleeping", "… and how are
you" and "… and tell me its name" stay with the picture, as the plan keeps them.
"""

from __future__ import annotations

from app.services.request_words import points_back, topic_words
from app.services.text_normalize import fold_token

SECOND_ASKS = frozenset({"explain", "tell", "write", "show", "help", "what", "how", "why", "who"})


def asks_separately(parts: list[str]) -> bool:
    """True for "… and (also) explain black holes": a request the plan answers apart."""
    words = [fold_token(part) for part in parts]
    for index, word in enumerate(words[:-1]):
        if word != "and":
            continue
        strong = words[index + 1] == "also"
        ask = index + 2 if strong else index + 1
        if ask < len(words) and words[ask] in SECOND_ASKS:
            rest = " ".join(parts[ask:])
            topics = topic_words(rest)
            if not topics or points_back(rest):
                return False
            return strong or not topics & topic_words(" ".join(parts[:index]))
    return False
