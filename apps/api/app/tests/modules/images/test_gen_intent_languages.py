"""Picture requests in the app's other languages read as English ones do.

"Zeichne eine Katze mit Hut" drew nothing: every rule read English words. Each case
here was None before ``gen_intent_local``.
"""

from __future__ import annotations

import pytest

from app.modules.images.gen_intent import extract_image_gen_prompt, picture_and_request
from app.modules.images.intent import composer_image_intent

# One plain "draw" request per app language (English for comparison).
DRAW = [
    ("en", "Draw a cat with a hat", "cat with a hat"),
    ("es", "Dibuja un gato con sombrero", "gato con sombrero"),
    ("fr", "Dessine un chat avec un chapeau", "chat avec un chapeau"),
    ("de", "Zeichne eine Katze mit Hut", "Katze mit Hut"),
    ("it", "Disegna un gatto con il cappello", "gatto con il cappello"),
    ("pt", "Desenhe um gato com chapéu", "gato com chapéu"),
    ("tr", "Şapkalı bir kedi çiz", "Şapkalı bir kedi"),
    ("ru", "Нарисуй кошку в шляпе", "кошку в шляпе"),
    ("am", "ድመት ሳልልኝ", "ድመት"),
]

# "Generate / create an image of …", the noun shape.
GENERATE = [
    ("en", "Generate an image of a lion", "a lion"),
    ("es", "Genera una imagen de un león", "un león"),
    ("fr", "Génère une image d'un lion", "un lion"),
    ("de", "Erstelle ein Bild von einem Löwen", "einem Löwen"),
    ("it", "Genera un'immagine di un leone", "un leone"),
    ("pt", "Gere uma imagem de um leão", "um leão"),
    ("tr", "Bir aslan resmi oluştur", "aslan"),
    ("ru", "Создай изображение льва", "льва"),
    ("am", "የአንበሳ ምስል ፍጠር", "አንበሳ"),
]

# Asked politely, with "me", or as a question, as English "can you draw me …" is.
POLITE = [
    ("Dessine-moi un mouton", "mouton"),
    ("Tu peux me dessiner un chat ?", "chat"),
    ("Kannst du mir bitte eine Katze zeichnen?", "Katze"),
    ("Zeichne bitte eine Katze", "Katze"),
    ("Zeichnen Sie eine Katze", "Katze"),
    ("Male mir einen Drachen", "Drachen"),
    ("¿Puedes dibujar un gato?", "gato"),
    ("Dibújame un perro", "perro"),
    ("Dibuja un gato, por favor", "gato"),
    ("Disegnami un drago", "drago"),
    ("Me desenhe um cachorro", "cachorro"),
    ("Pode desenhar um cachorro?", "cachorro"),
    ("Bana bir kedi çizer misin lütfen?", "kedi"),
    ("Нарисуй мне собаку", "собаку"),
    ("Можешь нарисовать собаку?", "собаку"),
    ("Erstelle ein realistisches Bild von einem Löwen", "einem Löwen"),
    ("Fais un dessin d'un chat", "un chat"),
    ("Сгенерируй картинку с котом", "с котом"),
    ("የድመት ስዕል ሳል", "ድመት"),
]

# Look-alikes: each English twin draws nothing either ("draw a conclusion", "draw me a
# table of the results", "draw a graph of y=x^2", "make a list", "draw it again").
NOT_A_PICTURE = [
    "Dibuja una conclusión",
    "dibuja el límite de 1/x cuando x tiende a 0",
    "dibuja la gráfica de y=x^2",
    "Dibuja un triángulo rectángulo",
    "Dibuja la molécula de etanol",
    "Dibuja una tabla con los resultados",
    "dibuja eso otra vez",
    "Crea una lista de compras",
    "Haz un plan de estudio",
    "Haz una foto",
    "Me encanta dibujar gatos",
    "Dessine le graphique de la fonction f(x)=x²",
    "dessine un triangle de côtés 3, 4 et 5",
    "Dessine un tableau des résultats",
    "Fais-moi une liste",
    "Je dessine un chat",
    "Zeichne mir eine Tabelle der Ergebnisse",
    "Zeichne den Graphen von y=x^2",
    "Zeichne ein Dreieck mit den Seiten 3, 4 und 5",
    "Zeichne die Strukturformel von Ethanol",
    "Zeichne ein Freikörperdiagramm",
    "Zeichne das Gespräch auf",
    "Mach dir ein Bild davon",
    "Erstelle einen Plan für meine Woche",
    "Zeichne das nochmal",
    "Male eine Katze",
    "Disegna il grafico di y=x^2",
    "Disegna una tabella dei risultati",
    "Disegni animati per bambini",
    "Fammi una lista della spesa",
    "Desenhe o gráfico de y=x^2",
    "Desenhe uma tabela com os resultados",
    "Crie uma lista de tarefas",
    "Нарисуй график функции",
    "Нарисуй таблицу результатов",
    "Нарисуй треугольник",
    "Нарисуй молекулу этанола",
    "Сделай список покупок",
    "Нарисуй это ещё раз",
    "Нарисуй картину будущего словами",
    "grafik çiz",
    "y=x^2 fonksiyonunun grafiğini çiz",
    "Bir tablo çiz",
    "önemli yerlerin altını çiz",
    "bir liste oluştur",
    "tekrar çiz",
    # Amharic "ሳል" is also "a cough": only "draw for me" or a picture noun draws.
    "ደረቅ ሳል",
    "ሳል እና ትኩሳት አለብኝ",
    "ግራፍ ሳልልኝ",
]

# A picture, then a second request in the same language (or English after it).
WITH_A_SECOND_REQUEST = [
    (
        "Dibuja un gato con sombrero y también explica qué es un agujero negro",
        "Dibuja un gato con sombrero",
        "explica qué es un agujero negro",
    ),
    (
        "Dessine un chat avec un chapeau et explique aussi ce qu'est un trou noir",
        "Dessine un chat avec un chapeau",
        "explique aussi ce qu'est un trou noir",
    ),
    (
        "Zeichne eine Katze mit Hut und erkläre auch, was ein schwarzes Loch ist",
        "Zeichne eine Katze mit Hut",
        "erkläre auch, was ein schwarzes Loch ist",
    ),
    (
        "Disegna un gatto con il cappello e spiega anche cos'è un buco nero",
        "Disegna un gatto con il cappello",
        "spiega anche cos'è un buco nero",
    ),
    (
        "Desenhe um gato com chapéu e também explique o que é um buraco negro",
        "Desenhe um gato com chapéu",
        "explique o que é um buraco negro",
    ),
    (
        "Şapkalı bir kedi çiz ve ayrıca kara deliğin ne olduğunu açıkla",
        "Şapkalı bir kedi çiz",
        "kara deliğin ne olduğunu açıkla",
    ),
    (
        "Нарисуй кошку в шляпе, а также объясни, что такое чёрная дыра",
        "Нарисуй кошку в шляпе",
        "объясни, что такое чёрная дыра",
    ),
    (
        "ድመት ሳልልኝ እንዲሁም ጥቁር ቀዳዳ ምን እንደሆነ አስረዳኝ",
        "ድመት ሳልልኝ",
        "ጥቁር ቀዳዳ ምን እንደሆነ አስረዳኝ",
    ),
    (
        "Zeichne eine Katze mit Hut and also explain what a black hole is",
        "Zeichne eine Katze mit Hut",
        "explain what a black hole is",
    ),
]


@pytest.mark.parametrize(("lang", "text", "subject"), DRAW + GENERATE)
def test_a_picture_request_reads_in_every_app_language(lang: str, text: str, subject: str) -> None:
    assert extract_image_gen_prompt(text) == subject, lang


@pytest.mark.parametrize(("lang", "text", "subject"), DRAW + GENERATE)
def test_the_composer_draws_it_as_the_chat_turn_would(lang: str, text: str, subject: str) -> None:
    intent = composer_image_intent(text, [])
    assert intent.lookup_query is None
    assert intent.request is not None and intent.request.prompt == subject, lang


@pytest.mark.parametrize(("text", "subject"), POLITE)
def test_polite_and_me_forms_read_as_english_ones_do(text: str, subject: str) -> None:
    assert extract_image_gen_prompt(text) == subject


@pytest.mark.parametrize("text", NOT_A_PICTURE)
def test_look_alikes_draw_nothing(text: str) -> None:
    assert extract_image_gen_prompt(text) is None
    assert picture_and_request(text) is None


@pytest.mark.parametrize(("text", "picture", "rest"), WITH_A_SECOND_REQUEST)
def test_a_second_request_is_not_part_of_the_picture(text: str, picture: str, rest: str) -> None:
    """The whole line draws nothing, as "draw a cat and also explain …" does; the planner
    takes the two parts."""
    assert extract_image_gen_prompt(text) is None
    assert picture_and_request(text) == (picture, rest)


@pytest.mark.parametrize(
    "text",
    [
        # A picture of more than one thing, or one described at length, is one request.
        "Dibuja un gato y un perro",
        "Dessine un chat qui danse et chante",
        "Zeichne eine Katze und auch einen Hund",
    ],
)
def test_a_longer_picture_is_still_one_picture(text: str) -> None:
    assert extract_image_gen_prompt(text)
    assert picture_and_request(text) is None


@pytest.mark.parametrize(
    "text",
    ["draw a conclusion from this", "make money", "create an image", "show me a picture of a cat"],
)
def test_english_reads_as_before(text: str) -> None:
    """The other languages are read only after every English rule declined."""
    assert extract_image_gen_prompt(text) is None
