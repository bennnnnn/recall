# ruff: noqa: RUF001, RUF002, RUF003 - Turkish dotless i, Cyrillic and maths signs are the words matched
"""Picture requests in the app's other languages: the word lists ``gen_intent_local`` reads.

English is ``gen_intent_words.py``; these are its shapes in Spanish, French, German,
Italian, Portuguese, Russian, Turkish and Amharic. "Draw" (dibuja, zeichne, нарисуй)
takes its subject; "create", "generate" and "make" need a picture noun first (erstelle
ein Bild von …), as "make a decision" is no picture in English either. A word in a
subject that the app draws itself, or that is no picture (a table, a graph, a limit, a
triangle, a molecule), keeps the request out of image generation, as its English twin
does. Words are lowercase; a phrase is a tuple of words.
"""

from __future__ import annotations

from dataclasses import dataclass, field


def _w(words: str) -> frozenset[str]:
    return frozenset(words.split())


def _stems(words: str) -> tuple[str, ...]:
    return tuple(words.split())


def _phrases(*phrases: str) -> tuple[tuple[str, ...], ...]:
    return tuple(tuple(phrase.split()) for phrase in phrases)


@dataclass(frozen=True)
class VerbFirst:
    """A language whose request starts with its verb: "Dibuja un gato con sombrero"."""

    code: str
    draw: frozenset[str]
    create: frozenset[str]
    # Verbs carrying their own "me": "dibújame", "disegnami".
    draw_me: frozenset[str] = frozenset()
    create_me: frozenset[str] = frozenset()
    # Verbs that draw only with a "me" word: German "male mir …" ("male" is an English word).
    needs_me: frozenset[str] = frozenset()
    # Verbs that draw only before an article, "me" or a picture noun: Spanish "pinta un
    # gato" paints, "¡pinta bien!" and "pinta que va a llover" say how something looks.
    needs_article: frozenset[str] = frozenset()
    me: frozenset[str] = frozenset()
    # "Mach dir ein Bild davon" (picture it yourself), "fais-toi une image": no picture.
    reflexive: frozenset[str] = frozenset()
    # Said between the verb and its object: "zeichne bitte …", "zeichne mal …".
    fillers: frozenset[str] = frozenset()
    # "¿Puedes …", "Kannst du …": an infinitive follows (German: closes the request).
    can_you: tuple[tuple[str, ...], ...] = ()
    draw_infinitives: frozenset[str] = frozenset()
    create_infinitives: frozenset[str] = frozenset()
    infinitive_last: bool = False
    # Portuguese "me desenhe um gato": the "me" comes before the verb.
    me_first: bool = False
    polite: tuple[tuple[str, ...], ...] = ()
    nouns: frozenset[str] = frozenset()
    of: frozenset[str] = frozenset()
    # A subject that points back ("eso", "das"): the chat names it, not the message.
    pronouns: frozenset[str] = frozenset()
    # Articles that are also pronouns ("la", "das"): one only when nothing follows.
    determiners: frozenset[str] = frozenset()
    again: tuple[tuple[str, ...], ...] = ()
    not_words: frozenset[str] = frozenset()
    not_stems: tuple[str, ...] = ()
    not_endings: tuple[str, ...] = ()
    not_pairs: frozenset[tuple[str, str]] = frozenset()
    # German separable verbs: "zeichne das Gespräch auf" records it.
    particles: frozenset[str] = frozenset()
    # What the picture is for ("para mi proyecto"): its words are not the subject.
    purpose: frozenset[str] = frozenset()


@dataclass(frozen=True)
class VerbLast:
    """A language whose verb closes the request: "Şapkalı bir kedi çiz"."""

    code: str
    draw: frozenset[str]
    create: frozenset[str]
    # "Çizer misin?": the verb, then the question word.
    asked_draw: frozenset[str] = frozenset()
    asked_create: frozenset[str] = frozenset()
    question: frozenset[str] = frozenset()
    # Amharic "ሳል" is also "a cough": a bare "draw" needs a picture noun before it.
    bare_draw: frozenset[str] = frozenset()
    me: frozenset[str] = frozenset()
    article: frozenset[str] = frozenset()
    polite: frozenset[str] = frozenset()
    nouns: frozenset[str] = frozenset()
    # Amharic "የድመት ምስል": "of" is the subject's first letter.
    of_prefix: str = ""
    pronouns: frozenset[str] = frozenset()
    again: tuple[tuple[str, ...], ...] = ()
    not_words: frozenset[str] = frozenset()
    not_stems: tuple[str, ...] = ()
    not_pairs: frozenset[tuple[str, str]] = field(default_factory=frozenset)
    # "Projem için bir kedi çiz": the words up to it say what the picture is for.
    purpose: frozenset[str] = frozenset()


SPANISH = VerbFirst(
    "es",
    purpose=_w("para"),
    draw=_w("dibuja dibujá dibuje dibujad pintá ilustra ilustre"),
    needs_article=_w("pinta pinte"),
    create=_w("crea creá cree genera generá genere haz haga diseña diseñe produce"),
    draw_me=_w("dibújame dibujame dibújeme dibujeme píntame pintame ilústrame"),
    create_me=_w("créame creame genérame generame hazme hágame hagame diséñame"),
    me=_w("me"),
    can_you=_phrases(
        "puedes",
        "podrías",
        "podrias",
        "podés",
        "puede",
        "podría",
        "podria",
        "me puedes",
        "me podrías",
        "me podrias",
        "me puede",
        "me podría",
    ),
    draw_infinitives=_w("dibujar dibujarme pintar pintarme ilustrar"),
    create_infinitives=_w("crear crearme generar generarme hacer hacerme diseñar diseñarme"),
    polite=_phrases("por favor", "porfa", "porfavor"),
    nouns=_w(
        "imagen imágenes imagenes dibujo dibujos foto fotos fotografía fotografia "
        "ilustración ilustracion ilustraciones retrato retratos pintura"
    ),
    of=_w("de del"),
    pronouns=_w("eso esto ello aquello ese esa este esta estos estas esos esas mí"),
    determiners=_w("lo la los las le"),
    again=_phrases("otra vez", "de nuevo", "nuevamente"),
    not_words=_w(
        "gráfica gráficas grafica graficas gráfico gráficos grafico graficos diagrama "
        "diagramas tabla tablas lista listas esquema esquemas cuadro cuadros "
        "conclusión conclusion conclusiones límite limite límites limites función funcion "
        "funciones derivada derivadas integral integrales ecuación ecuacion ecuaciones "
        "recta rectas línea linea líneas lineas segmento triángulo triangulo triángulos "
        "círculo circulo círculos cuadrado cuadrados rectángulo rectangulo polígono "
        "poligono trapecio rombo paralelogramo hipotenusa geometría geometria molécula "
        "molecula moléculas moleculas estructura estructuras fórmula formula plan planes "
        "horario cronograma organigrama"
    ),
    not_pairs=frozenset(
        {
            ("mapa", "conceptual"),
            ("mapa", "mental"),
            ("árbol", "genealógico"),
            ("arbol", "genealogico"),
            ("árbol", "de"),
            ("plano", "cartesiano"),
        }
    ),
)

FRENCH = VerbFirst(
    "fr",
    purpose=_w("pour"),
    draw=_w("dessine dessinez peins peignez illustre illustrez"),
    create=_w("crée créez cree creez génère générez genere generez fais faites conçois produis"),
    me=_w("moi me m'"),
    reflexive=_w("toi te t'"),
    can_you=_phrases(
        "peux tu",
        "pouvez vous",
        "pourrais tu",
        "pourriez vous",
        "tu peux",
        "vous pouvez",
        "tu pourrais",
        "vous pourriez",
    ),
    draw_infinitives=_w("dessiner peindre illustrer"),
    create_infinitives=_w("créer creer générer generer faire concevoir produire"),
    polite=_phrases(
        "s' il te plaît", "s' il te plait", "s' il vous plaît", "s' il vous plait", "stp", "svp"
    ),
    nouns=_w(
        "image images dessin dessins photo photos illustration illustrations portrait "
        "portraits peinture peintures"
    ),
    of=_w("de d' du des"),
    pronouns=_w("ça ca cela ceci ce cet cette ces moi"),
    determiners=_w("le la les l'"),
    again=_phrases("encore", "à nouveau", "a nouveau", "de nouveau"),
    not_words=_w(
        "graphique graphiques graphe graphes courbe courbes diagramme diagrammes schéma "
        "schémas schema tableau tableaux liste listes organigramme conclusion conclusions "
        "limite limites fonction fonctions dérivée derivee intégrale integrale équation "
        "equation équations droite droites ligne lignes segment triangle triangles cercle "
        "cercles carré carre carrés rectangle polygone trapèze losange parallélogramme "
        "hypoténuse géométrie geometrie molécule molecule molécules structure structures "
        "formule plan planning frise"
    ),
    not_pairs=frozenset(
        {
            ("carte", "mentale"),
            ("arbre", "généalogique"),
            ("arbre", "genealogique"),
            ("arbre", "de"),
        }
    ),
)

GERMAN = VerbFirst(
    "de",
    draw=_w("zeichne zeichnet zeichnen illustriere illustrieren"),
    create=_w(
        "erstelle erstell erstellen generiere generier generieren erzeuge erzeug erzeugen "
        "mache mach machen gestalte gestalten entwirf entwerfe entwerfen"
    ),
    needs_me=_w("male mal malen"),
    me=_w("mir uns ihr ihm"),
    reflexive=_w("dir dich sich euch"),
    # "Zeichnen Sie …" is the polite imperative; "sie" after another verb is "her".
    fillers=_w("bitte mal doch einfach sie"),
    can_you=_phrases("kannst du", "könntest du", "koenntest du", "können sie", "könnten sie"),
    draw_infinitives=_w("zeichnen malen illustrieren"),
    create_infinitives=_w("erstellen generieren erzeugen machen gestalten entwerfen"),
    infinitive_last=True,
    polite=_phrases("bitte"),
    nouns=_w(
        "bild bilder foto fotos zeichnung zeichnungen illustration illustrationen gemälde "
        "gemaelde porträt porträts portrait portraits"
    ),
    of=_w("von vom"),
    pronouns=_w("es dies dieses diese diesen ihn mir mich davon dazu darüber"),
    determiners=_w("das die den der"),
    again=_phrases("nochmal", "noch mal", "noch einmal", "erneut", "wieder"),
    not_words=_w(
        "graph graphen schaubild kurve kurven funktion funktionen ableitung integral "
        "gleichung gleichungen gerade geraden linie linien strecke dreieck dreiecke kreis "
        "kreise quadrat rechteck vieleck polygon trapez raute parallelogramm hypotenuse "
        "geometrie molekül moleküle molekuel struktur strukturen mindmap stammbaum "
        "entscheidungsbaum organigramm zeitstrahl schlussfolgerung fazit grenze grenzwert "
        "limes vertrag budget"
    ),
    # German joins nouns: "Freikörperdiagramm", "Wertetabelle", "Zeitplan".
    not_endings=_stems(
        "tabelle tabellen diagramm diagramme grafik graph plan liste kurve gleichung "
        "formel struktur"
    ),
    particles=_w("auf ab aus an ein vor"),
    purpose=_w("für"),
)

ITALIAN = VerbFirst(
    "it",
    purpose=_w("per"),
    # Not "disegni": it is also "drawings" ("disegni animati" are cartoons).
    draw=_w("disegna disegnate dipingi dipinga illustra"),
    create=_w("crea genera fai realizza produci"),
    draw_me=_w("disegnami dipingimi illustrami"),
    create_me=_w("creami generami fammi realizzami"),
    me=_w("mi"),
    can_you=_phrases(
        "puoi", "potresti", "può", "potrebbe", "mi puoi", "mi potresti", "mi può", "mi potrebbe"
    ),
    draw_infinitives=_w("disegnare disegnarmi dipingere dipingermi illustrare"),
    create_infinitives=_w("creare crearmi generare generarmi fare farmi realizzare realizzarmi"),
    polite=_phrases("per favore", "per piacere", "perfavore"),
    nouns=_w(
        "immagine immagini disegno foto fotografia illustrazione illustrazioni ritratto "
        "ritratti dipinto dipinti"
    ),
    of=_w("di del della dello dei degli delle d'"),
    pronouns=_w("questo questa quello quella questi queste quelli ciò cio me"),
    determiners=_w("lo la li le l'"),
    again=_phrases("di nuovo", "ancora"),
    not_words=_w(
        "grafico grafici diagramma diagrammi tabella tabelle elenco lista schema schemi "
        "conclusione conclusioni limite limiti funzione funzioni derivata integrale "
        "equazione equazioni retta rette linea linee segmento triangolo triangoli cerchio "
        "quadrato rettangolo poligono trapezio rombo parallelogramma ipotenusa geometria "
        "molecola molecole struttura strutture formula organigramma curva curve"
    ),
    not_pairs=frozenset(
        {("mappa", "concettuale"), ("mappa", "mentale"), ("albero", "genealogico"), ("piano", "di")}
    ),
)

PORTUGUESE = VerbFirst(
    "pt",
    purpose=_w("para"),
    draw=_w("desenhe desenha ilustre ilustra"),
    needs_article=_w("pinte pinta"),
    create=_w("crie cria gere gera faça faca faz produza"),
    me=_w("me"),
    can_you=_phrases(
        "pode", "você pode", "voce pode", "podes", "poderia", "você poderia", "consegue"
    ),
    draw_infinitives=_w("desenhar pintar ilustrar"),
    create_infinitives=_w("criar gerar fazer produzir"),
    me_first=True,
    polite=_phrases("por favor", "pfv"),
    nouns=_w(
        "imagem imagens desenho desenhos foto fotos fotografia ilustração ilustracao "
        "ilustrações retrato retratos pintura"
    ),
    of=_w("de do da dos das"),
    pronouns=_w("isso isto aquilo este esta esse essa aquele aquela estes estas esses essas mim"),
    determiners=_w("o a os as"),
    again=_phrases("de novo", "outra vez", "novamente"),
    not_words=_w(
        "gráfico grafico gráficos graficos diagrama diagramas tabela tabelas lista listas "
        "esquema quadro conclusão conclusao conclusões limite limites função funcao "
        "funções derivada integral equação equacao equações reta retas linha linhas "
        "segmento triângulo triangulo círculo circulo quadrado retângulo retangulo "
        "polígono poligono trapézio losango paralelogramo hipotenusa geometria molécula "
        "molecula moléculas estrutura estruturas fórmula formula plano cronograma "
        "organograma fluxograma"
    ),
    not_pairs=frozenset(
        {
            ("mapa", "mental"),
            ("mapa", "conceitual"),
            ("árvore", "genealógica"),
            ("arvore", "genealogica"),
        }
    ),
)

RUSSIAN = VerbFirst(
    "ru",
    purpose=_w("для"),
    draw=_w("нарисуй нарисуйте нарисуешь"),
    # "Изобрази удивление" asks to act surprised: with "мне" it draws.
    needs_me=_w("изобрази изобразите"),
    create=_w("создай создайте сгенерируй сгенерируйте сделай сделайте"),
    me=_w("мне нам"),
    can_you=_phrases(
        "можешь", "можете", "ты можешь", "вы можете", "мог бы", "могла бы", "могли бы"
    ),
    draw_infinitives=_w("нарисовать изобразить"),
    create_infinitives=_w("создать сгенерировать сделать"),
    polite=_phrases("пожалуйста", "плиз", "пж"),
    nouns=_w(
        "изображение изображения картинку картинка картинки картину картина рисунок "
        "рисунки фото фотографию фотография фотку иллюстрацию иллюстрация портрет арт"
    ),
    pronouns=_w("это этого эту этот эти его её ее их то того тот ту меня"),
    again=_phrases("ещё раз", "еще раз", "снова", "опять", "заново"),
    not_words=_w("граф графа графы план плана планы словами"),
    # Russian inflects: "график", "графика"; "таблицу", "таблица".
    not_stems=_stems(
        "график диаграм схем таблиц список списк функци предел производн интеграл "
        "уравнени прямую прямая лини отрез треугольник окружност круг квадрат "
        "прямоугольник многоугольник трапеци ромб параллелограмм гипотенуз геометри "
        "молекул структур формул вывод границ блок-схем интеллект-карт генеалогическ "
        "расписани"
    ),
)

TURKISH = VerbLast(
    "tr",
    draw=_w("çiz çizin çizsene çizermisin çizebilirmisin"),
    create=_w("oluştur oluşturun oluştursana üret üretin yap yapın yapsana tasarla tasarlayın"),
    asked_draw=_w("çizer çizebilir"),
    asked_create=_w("oluşturur oluşturabilir üretir üretebilir yapar yapabilir tasarlar"),
    question=_w("misin mısın musun müsün misiniz mısınız musunuz müsünüz"),
    me=_w("bana bize"),
    article=_w("bir"),
    polite=_w("lütfen lutfen"),
    nouns=_w(
        "resim resmi resmini görsel görseli görselini görüntü görüntüsü görüntüsünü "
        "fotoğraf fotoğrafı fotoğrafını foto fotosu fotosunu çizim çizimi çizimini "
        "illüstrasyon illüstrasyonu illüstrasyonunu portre portresi portresini"
    ),
    pronouns=_w("bunu onu şunu bunları onları şunları bu şu o"),
    again=_phrases("tekrar", "yine", "yeniden"),
    # "Altını çiz" underlines, "üstünü çiz" crosses out; "doğru" is a line.
    # Question words: "kedi nasıl çiz" is half a question.
    not_words=_w("altını altlarını üstünü üzerini doğru nasıl neden niye nedir"),
    purpose=_w("için"),
    not_stems=_stems(
        "grafi tablo liste diyagram şema akış fonksiyon türev integral limit denklem "
        "çizgi üçgen daire çember kare dikdörtgen çokgen yamuk paralelkenar hipotenüs "
        "geometri molekül yapı formül sonuç sınır plan takvim çizelge"
    ),
    not_pairs=frozenset(
        {("kavram", "harita"), ("soy", "ağac"), ("karar", "ağac"), ("yol", "harita")}
    ),
)

# Amharic: "draw for me" (ሳልልኝ) is never anything else; bare "ሳል" is also "a cough"
# ("ደረቅ ሳል", a dry cough), so it draws only after a picture noun ("የድመት ስዕል ሳል").
AMHARIC = VerbLast(
    "am",
    draw=_w("ሳልልኝ ሣልልኝ ሳይልኝ ሣይልኝ ሳሉልኝ ሣሉልኝ"),
    create=_w("ፍጠርልኝ ፍጠሪልኝ ፍጠሩልኝ ፍጠር ፍጠሪ ፍጠሩ አመንጭ አመንጪ አመንጩ"),
    bare_draw=_w("ሳል ሣል ሳይ ሣይ ሳሉ ሣሉ"),
    polite=_w("እባክህ እባክሽ እባካችሁ እባክዎ እባክዎን"),
    nouns=_w("ምስል ስዕል ሥዕል ስእል ፎቶ"),
    of_prefix="የ",
    pronouns=_w("ይህን ይሄን ያንን እሱን እሷን እነሱን"),
    again=_phrases("እንደገና"),
    not_words=_w("ክብ"),
    not_stems=_stems("ግራፍ ሰንጠረዥ ቻርት ዲያግራም ዝርዝር መስመር ማዕዘን ሞለኪውል ቀመር እኩልታ እቅድ"),
)

VERB_FIRST: tuple[VerbFirst, ...] = (SPANISH, PORTUGUESE, ITALIAN, FRENCH, GERMAN, RUSSIAN)
VERB_LAST: tuple[VerbLast, ...] = (TURKISH, AMHARIC)

# Articles any verb-first language may put before its object ("un", "eine", "uma").
ARTICLES = _w("un una uno un' une ein eine einen einem einer um uma")

# What joins a second request to a picture: "… und erkläre auch, was …", "… ve ayrıca …".
CONNECTORS = _w("and y e ed et und ve и а እና then luego después puis ensuite dann danach poi")
ALSO = _w(
    "also también además aussi également auch außerdem ausserdem zudem anche inoltre pure "
    "também tambem além disso ayrıca также тоже ещё еще እንዲሁም ደግሞ ደግሞም"
)
# A second request: one of these starts it (in Turkish and Amharic, a verb ends it).
# "Explain", "tell me": the verbs may follow a comma ("Нарисуй кошку, объясни …"). Only
# verbs that ask for an answer: "write its name below", "give it a hat", "show it smiling"
# and Turkish "yaz" (also "summer") add to the picture.
ASK_VERBS = _w(
    # English, for a picture asked in one language and the rest in English.
    "explain tell help "
    "explica explícame explicame explique dime cuéntame cuentame ayúdame ayudame enséñame "
    "traduce resume calcula resuelve describe "
    "expliquez dis dites raconte aide traduis résume calcule résous décris "
    "erkläre erklär erklären erklärt sag sage sagt erzähl erzähle hilf nenne übersetze "
    "fasse berechne löse beschreibe "
    "spiega spiegami dimmi raccontami racconta aiutami traduci riassumi calcola risolvi "
    "descrivi "
    "diga diz conte ajude traduza resuma calcule resolva descreva "
    "объясни объясните расскажи расскажите скажи скажите помоги помогите переведи "
    "посчитай реши опиши "
    "açıkla anlat söyle çevir özetle hesapla çöz "
    "አስረዳ አስረዳኝ አስረዱኝ አብራራ አብራራልኝ ንገረኝ ንገሪኝ ግለጽ"
)
# Question words, after "and" or a new sentence. Only words that ask: "como", "come", "как"
# are also "like", "quand", "когда", "где" open a clause about the picture ("et quand il
# dort"), "ne" is French, and "que", "che", "qui" describe it ("un chat qui danse").
ASK_QUESTIONS = _w(
    "what how why who "
    "qué cómo quién cuál cuáles dónde cuándo cuánto "
    "quel quelle quels quelles comment pourquoi combien "
    "was warum wieso weshalb wer wann welche welcher welches "
    "cosa cos' quale quali quanto "
    "quem qual quais quanto "
    "почему зачем кто какой какая какие сколько "
    "nedir nasıl neden niye kimdir "
    "ምን እንዴት ለምን ማን የት መቼ"
)
# Turkish and Amharic close a request with its verb or question word.
ASK_LAST = _w(
    "açıkla anlat söyle çevir özetle hesapla çöz nedir nasıl neden niye kimdir "
    "አስረዳ አስረዳኝ አስረዱኝ አብራራ አብራራልኝ ንገረኝ ንገሪኝ ግለጽ"
)
ASK_PAIRS = frozenset(
    {
        ("o", "que"),
        ("por", "qué"),
        ("por", "que"),
        ("qu'", "est-ce"),
        ("что", "такое"),
        ("что", "это"),
        ("как", "работает"),
    }
)
