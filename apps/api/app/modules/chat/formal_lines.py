# ruff: noqa: RUF001 -- the line is written in each reply language, Turkish too.
"""The line above a card the formal reader gave the server's value, in each reply language.

``formal_turn`` writes it; ``card_numbers`` reads it, so the server's own value keeps the
zeros it is known to (2.50 A is no model's padded 2.5).
"""

from __future__ import annotations

SERVER_VALUE_LINES = {
    "en": "Worked out again from the values in the question:",
    "es": "Calculado de nuevo con los valores de la pregunta:",
    "fr": "Recalculé à partir des valeurs de la question :",
    "pt": "Recalculado a partir dos valores da pergunta:",
    "ru": "Пересчитано по данным задачи:",
    "tr": "Sorudaki değerlerden yeniden hesaplandı:",
    "am": "ከጥያቄው እሴቶች እንደገና የተሰላ፦",
    "hi": "प्रश्न के मानों से फिर से गणना की गई:",
}


def server_valued(above: str) -> bool:
    """The text above a card ends on the formal reader's line: the card is the server's."""
    last = above.rstrip()
    return any(last.endswith(line) for line in SERVER_VALUE_LINES.values())
