# ruff: noqa: RUF001 - the words matched are the languages' own
"""The words a picture subject asked in another language may hold besides its nouns.

``gen_intent_drawable`` reads a subject word by word: each must be a listed noun
(``gen_intent_drawable_romance``, ``gen_intent_drawable_other``), a plain descriptor or a
function word from here. "Dibújame un gato negro en la playa" draws; "un gato en ASCII",
"un árbol binario", "una pizza dividida en fracciones", "un perro y sugiéreme nombres"
are answered in words, because "ASCII", "binario", "dividida" and "sugiéreme" are none.

- ``DESCRIBE``: colours, sizes, ages, simple looks and moods, a few poses ("sleeping",
  "flying": what a picture shows, never a task), simple art styles ("watercolour",
  "realistic", "futuristic"), the seasons and a few festive words used as looks
  ("snowy", "Christmas", "birthday"). Not "pixel art", "ASCII" or any other format.
  Each is written once, in the masculine singular; its other forms are made from it
  (``gen_intent_drawable``):
  "rojo" → roja, rojos, rojas; "красный" → красная, красного …; "काला" → काली, काले
  Irregular forms follow "/" ("beau/bel/belle/beaux").
- ``GLUE``: articles, "of", "with", "on", "in", "under", "next to", "near", "behind",
  "between", "my", numbers up to ten, "very". Places are built from these and listed nouns ("en la
  playa", "на луне", "पेड़ के नीचे").
- ``AND``: "and", allowed only between two drawable nouns ("un gato y un perro").

Amharic and Hindi are kept small on purpose (colours, sizes, a few looks) and want a native
review.
"""

from __future__ import annotations

DESCRIBE = {
    "es": """
rojo negro blanco azul/azules verde amarillo morado violeta gris/grises marrón/marrones
dorado plateado rosado celeste multicolor colorido pequeño pequeñito chiquito diminuto
grande/grandes gran enorme gigantesco mini viejo antiguo joven/jóvenes nuevo bonito lindo
hermoso precioso bello adorable tierno feo peludo esponjoso suave brillante oscuro mágico
encantado misterioso majestuoso valiente feroz/feroces salvaje gracioso divertido simpático
amigable feliz/felices alegre triste enojado sonriente dormido sentado alado nevado
futurista realista acuarela otoño invierno primavera verano navidad cumpleaños durmiendo
saltando volando nadando corriendo bailando jugando sonriendo surfeando tocando
""",
    "fr": """
rouge noir blanc/blanche/blancs/blanches bleu vert jaune violet/violette/violets/violettes
gris/grise/grises marron doré argenté rose orange multicolore coloré petit grand
gros/grosse/grosses énorme immense gigantesque minuscule mini géant
vieux/vieil/vieille/vieilles jeune nouveau/nouvel/nouvelle/nouveaux/nouvelles
ancien/ancienne/anciens/anciennes beau/bel/belle/beaux/belles joli
mignon/mignonne/mignons/mignonnes adorable magnifique superbe drôle poilu doux/douce
brillant sombre magique enchanté mystérieux/mystérieuse/mystérieuses
majestueux/majestueuse/majestueuses courageux/courageuse féroce sauvage
gentil/gentille/gentils/gentilles sympa amical/amicale/amicaux heureux/heureuse
joyeux/joyeuse triste fâché souriant endormi assis enneigé ailé futuriste réaliste automne
hiver printemps été aquarelle noël anniversaire dort joue vole nage court saute danse sourit
""",
    "pt": """
vermelho preto negro branco azul/azuis verde amarelo roxo violeta cinza cinzento marrom
castanho dourado prateado rosa laranja colorido pequeno pequenino grande/grandes enorme
gigante/gigantes gigantesco minúsculo mini velho antigo jovem/jovens novo belo lindo bonito
fofo adorável/adoráveis simpático magnífico estranho misterioso majestoso corajoso
feroz/ferozes selvagem engraçado divertido peludo macio brilhante escuro mágico encantado
feliz/felizes alegre triste zangado sorridente sentado adormecido nevado alado futurista
realista aquarela outono inverno primavera verão natal aniversário dormindo pulando saltando
voando nadando correndo dançando brincando sorrindo surfando tocando
""",
    "ru": """
красный чёрный белый синий голубой зелёный жёлтый фиолетовый серый коричневый золотой
серебряный розовый оранжевый разноцветный маленький большой огромный крошечный гигантский
старый древний молодой новый милый красивый симпатичный пушистый мягкий яркий тёмный
волшебный заколдованный таинственный величественный храбрый смелый дикий весёлый смешной
забавный счастливый грустный добрый улыбающийся спящий летающий летящий бегущий танцующий
плавающий сидящий заснеженный футуристический осенний зимний весенний летний осенью зимой
весной летом пиратский солнечный реалистичный новогодний рождественский праздничный
воздушный акварелью
""",
    "tr": """
kırmızı siyah kara beyaz mavi yeşil sarı mor gri kahverengi altın gümüş pembe turuncu renkli
rengarenk küçük büyük kocaman minik minicik yaşlı eski genç yeni sevimli tatlı güzel şirin
tüylü yumuşak parlak karanlık büyülü gizemli görkemli cesur vahşi komik neşeli mutlu üzgün
kızgın gülümseyen uyuyan uçan koşan yüzen oturan karlı fütüristik sonbaharda kışın
ilkbaharda yazın gerçekçi suluboya yılbaşı noel doğum günü kardan
""",
    "am": "ቀይ ጥቁር ነጭ ሰማያዊ አረንጓዴ ቢጫ ትንሽ ትልቅ ቆንጆ",
    "hi": """
लाल काला सफ़ेद/सफेद नीला पीला हरा भूरा गुलाबी बैंगनी नारंगी सुनहरा चाँदी/चांदी स्लेटी
छोटा बड़ा/बडा प्यारा सुंदर/सुन्दर खुश उदास मोटा पतला लंबा/लम्बा पुराना नया/नई/नए/नयी
जादुई उड़ता/उड़ती/उड़ते सोता/सोती/सोते रंगीन चमकीला
""",
}

GLUE = {
    "es": """
un una unos unas el la los las de del al a en con sobre bajo debajo encima junto lado cerca
entre detrás delante mi mis muy súper super dos tres cuatro cinco seis siete ocho nueve diez
varios varias muchos muchas
""",
    "fr": """
un une des de du d' l' le la les au aux à dans sur sous avec près côté devant derrière entre
en qui mon ma mes très super deux trois quatre cinq six sept huit neuf dix plusieurs
quelques
""",
    "pt": """
um uma uns umas o a os as de do da dos das em no na nos nas num numa com sob sobre ao à aos
lado perto entre atrás frente meu minha meus minhas muito super dois duas três quatro cinco
seis sete oito nove dez alguns algumas
""",
    "ru": """
в во на с со под над у около рядом возле среди между за перед мой моя моё мои моего моей
моих моим мою очень супер два две три четыре пять шесть семь восемь девять десять двух трёх
четырёх пару несколько нескольких много божья божью божьей
""",
    "tr": """
bir iki üç dört beş altı yedi sekiz dokuz on çok süper ile üstünde üzerinde altında arasında
yanında içinde önünde arkasında kenarında
""",
    "am": "ላይ ውስጥ ጋር",
    "hi": """
एक दो तीन चार पाँच पांच का की के में पर से साथ नीचे ऊपर पास बीच पीछे सामने अंदर बाहर
वाला वाली वाले मेरा मेरी मेरे बहुत
""",
}

AND = {
    "es": "y e",
    "fr": "et",
    "pt": "e",
    "ru": "и",
    "tr": "ve",
    "am": "እና",
    "hi": "और तथा",
}

# Amharic writes "of", "in" and "from" as a noun's first letter ("የድመት", "በጫካ").
AMHARIC_PREFIXES = "የ በ ከ"
