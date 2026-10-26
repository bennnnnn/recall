"""Round four of parity with English on main: misfires first, then clear misses.

A misfire (a picture drawn where the user wanted words) costs a daily picture and the
answer; a miss leaves the model to answer, as main does. Each line was checked against
its English translation on main.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.chat.turn_prep.intents import plan_turn
from app.modules.images.gen_intent import extract_image_gen_prompt
from app.modules.images.gen_intent_parts import picture_language
from app.modules.images.intent import composer_image_intent, image_gen_request

# Drawn on the previous version, nothing here asks for a picture (or English declines it):
# German everyday "mal", lists, boundaries, databases, German compounds, Russian and
# Turkish plurals and cases, a slope's other inflection.
NOT_DRAWN = [
    "Mal den Teufel nicht an die Wand",
    "Mal die Situation nicht so schwarz",
    "Mal die Hand aufs Herz, wer war das?",
    "Mal einen Kaffee trinken?",
    "Mal ein Gedanke: sollten wir umziehen?",
    "Mal ein Kompliment an dich: du bist toll",
    "Mal ein anderes Thema: was kochen wir heute?",
    "Dibuja una lista de las capitales de Europa",
    "Dessine une liste des capitales européennes",
    "Zeichne mir eine Liste der Hauptstädte",
    "Disegna un elenco delle capitali europee",
    "Desenhe uma lista das capitais da Europa",
    "Нарисуй список столиц Европы",
    "Avrupa başkentlerinin bir listesini çiz",
    "Dibuja la frontera entre España y Francia",
    "Zeichne die Grenze zwischen Deutschland und Polen",
    "Dibuja la base de datos de mi tienda",
    "Zeichne die Datenbank meines Shops",
    "Zeichne ein Säulendiagramm",
    "Zeichne ein Kreisdiagramm meiner Ausgaben",
    "Zeichne den Funktionsgraphen",
    "Нарисуй треугольники",
    "Нарисуй квадраты",
    "Нарисуй схемы",
    "Нарисуй диаграмм",
    "Üçgenler çiz",
    "Нарисуй структурную формулу этанола",
    "Zeichne die Kräfte auf einen Block auf einer geneigten Ebene",
    "Dessine un tableau des résultats",
]

# Missed on the previous version; each English twin draws on main.
DRAWN = [
    "Mal mir einen Drachen",
    "Male eine Katze mit Hut",
    "Genera una foto di un gatto",
    "Crea una foto di un gatto",
    "Desenhe o mar ao pôr do sol",
    "Desenhe o Cristo Redentor",
    "Desenhe o gato de botas",
    "Pinte o céu estrelado",
    "Me desenhe o Pikachu",
    "Você pode desenhar o meu cachorro?",
    "Ilustre o Pequeno Príncipe",
    "Dessine le plus beau chat du monde",
    "Dessine la plus grande montagne du monde",
    "Dibuja la más bonita de las flores",
    "Dibuja lo más bonito que se te ocurra",
    "Zeichne die vier Jahreszeiten",
    "Zeichne die super süße Katze",
    "Zeichne die unter dem Baum schlafende Katze",
    "Zeichne die immer größer werdende Welle",
    "Zeichne die mit Blumen bedeckte Wiese",
    "Zeichne das in der Nacht leuchtende Schloss",
    "Zeichne die noch nie gesehene Kreatur",
    "Pinte el mar",
    "Pinta el mar",
    "Denize doğru koşan bir at çiz",
    "Güneşe doğru uçan bir kuş çiz",
    "Eğri bir ağaç çiz",
    "Eski bir eğri köprü çiz",
    "Giriş kapısı kırmızı olan bir ev çiz",
    "Bir oyun parkında çocuklar çiz",
    "Нарисуй графа Дракулу",
    "Нарисуй графа в замке",
    "Нарисуй линию горизонта на закате",
    "Нарисуй совет директоров из котов",
    "Disegna una coppia in una relazione felice",
    "Disegna file di alberi lungo un viale",
    "Disegna una macchina in curva",
    "Desenhe um gato em primeiro plano",
    "Desenhe uma estrada com curvas",
    "Pinte uma tela com flores",
    "Desenhe um colar de contas",
    "Desenhe uma nota de cem reais",
    "Dibuja un perro en una tabla de surf",
    "Dibuja un collar de cuentas",
    "Dibuja un reloj a prueba de agua",
    "Dibuja una carretera con curvas",
    "Dessine un tableau de Monet",
    "Dessine un chat devant le tableau noir",
    "Dessine le plan de Paris",
    "Dessine un site archéologique",
    "Dessine un conte de fées",
    "Zeichne eine Katze in einem Satz über den Zaun",
    "Zeichne die kleiner werdende Kerze",
    "Desenhe o ciclo da água",
    "Kare şeklinde bir pencere çiz",
    "Bir daire içinde bir yıldız çiz",
    "Bir oyun oynayan çocuklar çiz",
]


@pytest.mark.parametrize("text", NOT_DRAWN)
def test_no_picture(text: str) -> None:
    assert composer_image_intent(text, []).request is None
    assert not plan_turn(text).of_kind("image")


@pytest.mark.parametrize("text", DRAWN)
def test_a_picture(text: str) -> None:
    assert composer_image_intent(text, []).request is not None


@pytest.mark.parametrize(
    "text",
    [
        "draw me a cat and how are you",
        "draw me a cat and how",
        "draw me a castle and help",
        "draw me a cat and who",
    ],
)
def test_english_draw_me_with_no_request_after_and_draws_as_on_main(text: str) -> None:
    """Main's plan does not cut "… and how are you": the whole line is the picture."""
    assert extract_image_gen_prompt(text)


@pytest.mark.parametrize("text", ["Genera una foto di un gatto", "Crea una foto di un gatto"])
def test_italian_shared_verbs_read_as_italian(text: str) -> None:
    """ "una" is Spanish and Italian; "di" is Italian alone: "a photo of a cat"."""
    assert extract_image_gen_prompt(text) == "un gatto"
    assert picture_language(text) == "it"


_AFTER_A_PICTURE = [
    SimpleNamespace(role="user", content="Generate image: black cat"),
    SimpleNamespace(
        role="assistant", content="[Image: /attachments/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/file]"
    ),
]


@pytest.mark.parametrize(
    "text",
    [
        "Dessine le plus beau chat du monde",
        "Dessine la plus grande montagne du monde",
        "Dibuja la más bonita de las flores",
        "Zeichne die vier Jahreszeiten",
        "Zeichne die unter dem Baum schlafende Katze",
        "Zeichne die mit Blumen bedeckte Wiese",
        "Zeichne das in der Nacht leuchtende Schloss",
    ],
)
def test_a_new_picture_after_a_picture_is_not_a_revision(text: str) -> None:
    request = image_gen_request(text, _AFTER_A_PICTURE)
    assert request is not None and not request.revision


@pytest.mark.parametrize("text", ["Zeichne das hier", "Dibuja eso aquí"])
def test_this_here_points_back(text: str) -> None:
    assert extract_image_gen_prompt(text) is None
