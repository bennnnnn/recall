"""Draft asks and draft changes in the app's other seven languages get the draft contract.

Before, only "escribe un correo", "escreva um e-mail" and "напиши письмо" were read,
and only as an email: a French, German, Italian, Turkish or Amharic email, any message
or post, and every change to a draft ("más corto", "auf Englisch") got the no-draft
rule ("do not create an email, message ... fence"), so the draft lost its card.
"""

from __future__ import annotations

import pytest

from app.modules.chat.prompt_constants import NON_DRAFT_TURN_HINT, draft_followup_hint
from app.modules.chat.prompt_constants.writing import (
    EMAIL_ASK_PURPOSE_HINT,
    EMAIL_DRAFT_HINT,
    SOCIAL_DRAFT_HINT,
)
from app.modules.chat.prompt_format import _style_format_hints
from app.modules.turn_reading.writing import draft_followup
from app.modules.turn_reading.writing_kind import writing_request_kind
from app.modules.turn_reading.writing_purpose import is_underspecified_writing_request


def _hints(text: str, prior: list[tuple[str, str]] | None = None) -> list[str]:
    return _style_format_hints(
        query_text=text,
        is_day_plan=False,
        minimal_personal_context=False,
        prior_messages=prior,
    )


@pytest.mark.parametrize(
    ("text", "kind", "bare"),
    [
        # Spanish
        ("escríbeme un correo", "email", True),
        ("escribe un correo a mi jefe pidiendo el viernes libre", "email", False),
        ("¿puedes escribir un correo a mi jefe?", "email", True),
        ("escríbeme un mensaje para mi jefe diciendo que llegaré tarde mañana", "message", False),
        ("manda un mensaje a mi jefe diciendo que estoy enfermo", "message", False),
        ("escribe una publicación de LinkedIn sobre mi ascenso", "social", False),
        # French
        ("écris un email à mon patron pour demander mon vendredi", "email", False),
        ("écris un e-mail à mon patron", "email", True),
        (
            "écris un message à mon propriétaire pour dire que le chauffage est en panne",
            "message",
            False,
        ),
        ("écris un post LinkedIn sur ma promotion", "social", False),
        # Portuguese
        ("escreva um e-mail para meu chefe pedindo sexta de folga", "email", False),
        (
            "escreve uma mensagem para o meu senhorio a dizer que o aquecimento avariou",
            "message",
            False,
        ),
        # Russian
        ("напиши письмо начальнику", "email", True),
        ("напиши письмо начальнику с просьбой дать выходной в пятницу", "email", False),
        ("напиши сообщение арендодателю, что не работает отопление", "message", False),
        ("напиши пост для LinkedIn о моём повышении", "social", False),
        # Turkish and Amharic end on the verb.
        ("patronuma bir e-posta yaz", "email", True),
        ("patronuma cuma günü izin istediğimi anlatan bir e-posta yaz", "email", False),
        ("ev sahibime kaloriferin bozulduğunu söyleyen bir mesaj yaz", "message", False),
        ("LinkedIn için bir gönderi yaz", "social", True),
        ("ለአለቃዬ ኢሜይል ጻፍ", "email", True),
        ("ለአለቃዬ ዓርብ እረፍት የሚጠይቅ ኢሜይል ጻፍልኝ", "email", False),
        ("ለእናቴ መልእክት ጻፍልኝ", "message", True),
        # Hindi ends on the verb too; what the draft says may follow it.
        ("मेरे बॉस को एक ईमेल लिखो", "email", True),
        ("मेरे बॉस के लिए एक ईमेल लिखो जिसमें शुक्रवार की छुट्टी माँगी हो", "email", False),
        ("बॉस को ईमेल लिखो कि मैं कल नहीं आऊँगा", "email", False),
        ("माँ को एक मैसेज लिख दो", "message", True),
        ("लिंक्डइन के लिए एक पोस्ट लिखो", "social", True),
    ],
)
def test_a_draft_ask_in_another_language_is_that_draft(text: str, kind: str, bare: bool) -> None:
    assert writing_request_kind(text) == kind
    assert is_underspecified_writing_request(text) is bare
    parts = _hints(text)
    contract = {"email": EMAIL_DRAFT_HINT, "message": EMAIL_DRAFT_HINT}.get(kind, SOCIAL_DRAFT_HINT)
    assert (EMAIL_ASK_PURPOSE_HINT if bare else contract) in parts
    assert NON_DRAFT_TURN_HINT not in parts


@pytest.mark.parametrize(
    "text",
    [
        # A text about something, a summary of an email, an email that broke.
        "escribe un texto sobre el cambio climático",
        "escreva um texto sobre a amazônia",
        "escribe un resumen de este correo",
        "bu e-postanın özetini yaz",
        "explica qué es un correo electrónico",
        "mi correo no funciona",
        "manda saludos a tu madre",
        "इस ईमेल का सारांश लिखो",
        "मेरा ईमेल काम नहीं कर रहा",
    ],
)
def test_other_lines_with_a_draft_word_are_not_drafts(text: str) -> None:
    assert writing_request_kind(text) is None


_EMAIL = "```email\nAsunto: Viernes libre\n\nHola Sara:\n\n¿Podría tomarme el viernes libre?\n```"
_TEXT = "```message\nHola Sam, llego 15 minutos tarde. ¡Perdón!\n```"


@pytest.mark.parametrize(
    "text",
    [
        "más corto",
        "hazlo más formal",
        "¿puedes hacerlo más corto?",
        "tradúcelo al inglés",
        "en inglés",
        "añade que vuelvo el lunes",
        "plus court",
        "peux-tu le rendre plus formel",
        "en anglais",
        "mais curto",
        "em inglês",
        "короче",
        "на английском",
        "добавь, что я вернусь в понедельник",
        "daha kısa yap",
        "İngilizceye çevir",
        "pazartesi döneceğimi de ekle",
        "አሳጥረው",
        "በእንግሊዝኛ",
        "और छोटा करो",
        "इसे थोड़ा औपचारिक बना दो",
        "अंग्रेज़ी में लिखो",
        "इसका अनुवाद करो",
        "कि मैं सोमवार को लौटूँगा, यह भी जोड़ो",
        # Spanish names German, a language a user may ask for though the app has none.
        "en alemán",
    ],
)
def test_a_change_in_another_language_revises_the_draft(text: str) -> None:
    prior = [
        ("user", "escribe un correo a mi jefe pidiendo el viernes libre"),
        ("assistant", _EMAIL),
    ]
    assert draft_followup(text, prior) == ("email", True)
    parts = _hints(text, prior)
    assert draft_followup_hint("email", drafted=True) in parts
    assert NON_DRAFT_TURN_HINT not in parts


@pytest.mark.parametrize(
    "text",
    [
        "¿qué es más largo, el Nilo o el Amazonas?",
        "muchas gracias, perfecto",
        "cuál es la capital de Francia?",
        "क्या यह छोटा है?",
        "धन्यवाद, बढ़िया",
    ],
)
def test_a_question_or_thanks_after_a_draft_is_not_a_change(text: str) -> None:
    assert draft_followup(text, [("user", "escríbele a Sam"), ("assistant", _TEXT)]) is None
