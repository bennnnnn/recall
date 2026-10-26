# ruff: noqa: RUF001, RUF003 - Turkish dotless i and Cyrillic are the words matched
"""What a picture request in another language may not be about: the twins of English
``NON_IMAGE_WORDS``, and the maths, physics and chemistry the app answers itself.

"Ilustra con un ejemplo", "Illustriere die Lösung", "Нарисуй пример", "Bir örnek çiz" are
teaching asks; English "illustrate with an example" and "draw an example" draw nothing
(``gen_intent_words.NON_IMAGE_WORDS``). "Dibuja la cafeína", "Zeichne die Kräfte auf einen
Block", "Нарисуй силы …" are chemistry and physics, which English hands to the subject
(``stem_subject_claims``, English only). In a teaching app a doubt is no picture: a word
here keeps the request out of image generation, and the model answers in words.

Romance and German words list their singular, and a plural ending is tried off
(``plurals``); Italian lists both forms. Russian and Turkish inflect, so most of theirs are
stems. A pair is two neighbouring words, each matched by its start ("campo eléctrico").
The Amharic words are a best effort and want a native speaker's review.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import pairwise


def _w(words: str) -> frozenset[str]:
    return frozenset(words.split())


def _stems(words: str) -> tuple[str, ...]:
    return tuple(words.split())


def _pairs(words: str) -> frozenset[tuple[str, str]]:
    """ "campo eléctr plano inclinado": word starts, two by two."""
    split = words.split()
    return frozenset(zip(split[::2], split[1::2], strict=True))


@dataclass(frozen=True)
class Topics:
    words: frozenset[str]
    stems: tuple[str, ...] = ()
    pairs: frozenset[tuple[str, str]] = field(default_factory=frozenset)
    plurals: tuple[str, ...] = ()
    # German compounds: "Matheaufgabe", "Natriumchlorid", "Essigsäure".
    endings: tuple[str, ...] = ()

    def names_one(self, words: list[str]) -> bool:
        """True when one of ``words`` (lowercase) is a topic here."""
        for word in words:
            if word in self.words or (self.stems and word.startswith(self.stems)):
                return True
            if self.endings and word.endswith(self.endings):
                return True
            for ending in self.plurals:
                if word.endswith(ending) and word[: -len(ending)] in self.words:
                    return True
        return any(
            first.startswith(a) and second.startswith(b)
            for first, second in pairwise(words)
            for a, b in self.pairs
        )


SPANISH = Topics(
    _w(
        # Tasks, school and writing: "Ilustra con un ejemplo", "Dibuja mi tarea".
        "tarea deberes recordatorio proyecto cuenta script código codigo clase archivo "
        "carpeta chat nota apunte resumen evento reunión reunion cuestionario quiz examen "
        "prueba correo email mensaje respuesta borrador informe reporte componente página "
        "pagina pantalla botón boton formulario usuario contraseña commit error bug test "
        "comparación comparacion ejemplo problema ejercicio solución solucion demostración "
        "ficha actividad consejo truco secreto hábito habito etapa fase música musica "
        "canción cancion playlist app aplicación aplicacion web juego programa html css "
        "javascript receta poema ensayo redacción historia cuento chiste párrafo parrafo "
        "frase oración introducción título biografía tuit eslogan idea consulta sql json "
        "entrenamiento rutina itinerario currículum curriculum cv discurso presupuesto "
        "factura encuesta contrato presentación presentacion diapositiva adivinanza "
        "acertijo crucigrama diferencia lección leccion pregunta "
        # Maths, physics and chemistry.
        "fuerza molécula compuesto estructura reacción reaccion circuito vector onda "
        "célula celula átomo atomo elemento fórmula ecuación diagrama velocidad "
        "aceleración energía voltaje electrón electron protón neutrón ion ión enlace ácido "
        "rayos parábola ángulo angulo hipérbola acido isómero polímero adn proteína fotosíntesis "
        "mitosis polea "
        # Compounds chemistry draws as a structure ("draw caffeine").
        "cafeína cafeina benceno etanol metanol aspirina glucosa sacarosa metano etano "
        "propano butano amoníaco amoniaco acetona ozono colesterol dopamina serotonina "
        "nicotina paracetamol ibuprofeno insulina penicilina morfina adrenalina dióxido "
        "monóxido óxido oxido cloruro sulfato nitrato hidróxido carbonato fenol tolueno "
        "glicerol urea formaldehído cloroformo mentol"
    ),
    pairs=_pairs(
        "campo eléctr campo electr campo magnét campo magnet campo gravit plano inclinado lente "
        "conv lente conc "
        "corriente eléctrica"
    ),
    plurals=("s", "es"),
)

FRENCH = Topics(
    _w(
        # Not "chat": it is a cat.
        "tâche devoir rappel projet compte script code fonction classe fichier dossier note "
        "résumé événement réunion quiz questionnaire examen fiche mail email courriel "
        "message réponse brouillon rapport composant page écran bouton formulaire "
        "utilisateur commit bug erreur test comparaison exemple problème exercice solution "
        "démonstration preuve conseil astuce secret habitude étape phase musique chanson "
        "playlist appli application site jeu programme html css javascript recette poème "
        "dissertation rédaction histoire blague paragraphe phrase introduction titre bio "
        "biographie tweet slogan idée requête sql json entraînement routine itinéraire cv "
        "discours budget facture sondage contrat présentation diapositive devinette énigme "
        "différence leçon question "
        "force molécule composé structure réaction circuit vecteur onde cellule atome "
        "élément formule équation diagramme vitesse accélération énergie électron proton "
        "neutron ion liaison rayons parabole angle hyperbole acide isomère polymère adn protéine "
        "photosynthèse mitose poulie "
        "caféine benzène éthanol méthanol aspirine glucose saccharose méthane éthane propane "
        "butane ammoniac acétone ozone cholestérol dopamine sérotonine nicotine paracétamol "
        "ibuprofène insuline pénicilline morphine adrénaline dioxyde monoxyde oxyde chlorure "
        "sulfate nitrate hydroxyde carbonate phénol toluène glycérol urée chloroforme menthol"
    ),
    pairs=_pairs(
        "champ électr champ electr champ magnét champ magnet plan incliné rayon lumin lentille "
        "conv lentille diverg mots croisés"
    ),
    plurals=("s", "x"),
)

GERMAN = Topics(
    _w(
        "aufgabe hausaufgabe erinnerung projekt konto skript code funktion klasse datei "
        "ordner chat notiz zusammenfassung termin ereignis meeting besprechung quiz test "
        "prüfung karteikarte mail email e-mail nachricht antwort entwurf bericht komponente "
        "bildschirm button formular benutzer passwort commit fehler bug vergleich beispiel "
        "problem übung lösung beweis arbeitsblatt tipp trick geheimnis gewohnheit phase "
        "musik lied song playlist app webseite website spiel programm html css javascript "
        "rezept gedicht aufsatz essay geschichte witz absatz satz einleitung gliederung "
        "überschrift titel bio tweet slogan idee abfrage sql json training workout routine "
        "reiseplan lebenslauf cv rede rechnung umfrage präsentation folie rätsel "
        "kreuzworträtsel unterschied lektion frage "
        "kraft kräfte molekül verbindung reaktion schaltung schaltkreis stromkreis "
        "magnetfeld kraftfeld vektor welle zelle atom element geschwindigkeit beschleunigung "
        "energie strahlengang sammellinse zerstreuungslinse lichtstrahlen parabel winkel "
        "hyperbel elektron proton neutron ion bindung säure isomer polymer dna protein "
        "photosynthese fotosynthese mitose flaschenzug "
        "koffein coffein benzol ethanol methanol aspirin glukose glucose saccharose methan "
        "ethan propan butan ammoniak aceton ozon cholesterin dopamin serotonin nikotin "
        "paracetamol ibuprofen insulin penicillin morphin adrenalin phenol toluol glycerin "
        "harnstoff chloroform menthol"
    ),
    pairs=_pairs(
        "schiefe ebene schiefen ebene elektrische feld elektrisches feld magnetische feld "
        "magnetisches feld"
    ),
    plurals=("e", "en", "n", "s", "er"),
    endings=_stems(
        "aufgabe aufgaben beispiel beispiele säure oxid chlorid sulfat nitrat hydroxid "
        "carbonat zelle zellen molekül moleküle kräfte reaktion übung übungen lösung "
        "lösungen welle wellen"
    ),
)

ITALIAN = Topics(
    _w(
        "compito compiti promemoria progetto progetti account script codice funzione "
        "funzioni classe file cartella chat nota note appunti riassunto sintesi evento "
        "eventi riunione quiz questionario esame verifica email mail messaggio risposta "
        "bozza relazione rapporto componente pagina schermo pulsante modulo utente password "
        "commit errore bug test confronto esempio esempi problema problemi esercizio "
        "esercizi soluzione soluzioni dimostrazione prova scheda consiglio consigli trucco "
        "segreto abitudine fase tappa musica canzone playlist app applicazione sito gioco "
        "programma html css javascript ricetta poesia tema saggio storia racconto "
        "barzelletta paragrafo frase introduzione titolo didascalia biografia tweet slogan "
        "idea idee query sql json allenamento routine itinerario curriculum cv discorso "
        "budget bilancio fattura sondaggio contratto presentazione diapositiva slide "
        "indovinello cruciverba differenza lezione domanda domande "
        "forza forze molecola molecole composto struttura reazione reazioni circuito "
        "vettore onda onde cellula atomo atomi elemento formula equazione diagramma "
        "raggi parabola angolo iperbole velocità accelerazione energia elettrone protone "
        "neutrone ione legame acido "
        "isomero polimero dna proteina fotosintesi mitosi carrucola "
        "caffeina benzene etanolo metanolo aspirina glucosio saccarosio metano etano "
        "propano butano ammoniaca acetone ozono colesterolo dopamina serotonina nicotina "
        "paracetamolo ibuprofene insulina penicillina morfina adrenalina anidride biossido "
        "ossido cloruro solfato nitrato idrossido carbonato fenolo toluene glicerolo urea "
        "cloroformio mentolo"
    ),
    pairs=_pairs("campo elettr campo magnet campo gravit piano inclinato lente conv lente diverg"),
)

PORTUGUESE = Topics(
    _w(
        "tarefa lição licao dever lembrete projeto conta script código codigo função funcao "
        "classe arquivo chat nota anotação resumo evento reunião quiz questionário prova "
        "exame email e-mail mensagem resposta rascunho relatório componente página pagina "
        "tela botão formulário usuário senha commit erro bug teste comparação exemplo "
        "problema exercício exercicio solução solucao demonstração ficha dica truque "
        "segredo hábito etapa fase música musica canção playlist app aplicativo site jogo "
        "programa planilha html css javascript receita poema redação ensaio história "
        "piada parágrafo frase introdução título legenda biografia tweet slogan ideia "
        "consulta sql json treino rotina roteiro currículo cv discurso orçamento fatura "
        "pesquisa contrato apresentação slide charada enigma diferença questão pergunta "
        "funções soluções comparações lições questões apresentações reuniões canções "
        "redações introduções demonstrações anotações "
        "força molécula composto estrutura reação reações circuito vetor onda célula átomo "
        "elemento fórmula equação equações diagrama velocidade aceleração energia elétron "
        "raios parábola ângulo angulo hipérbole próton nêutron íon ligação ligações ácido "
        "isômero polímero dna proteína "
        "fotossíntese mitose polia "
        "cafeína cafeina benzeno etanol metanol aspirina glicose sacarose metano etano "
        "propano butano amônia amonia amoníaco acetona ozônio colesterol dopamina "
        "serotonina nicotina paracetamol ibuprofeno insulina penicilina morfina adrenalina "
        "dióxido monóxido óxido cloreto sulfato nitrato hidróxido carbonato fenol tolueno "
        "glicerol ureia clorofórmio mentol"
    ),
    pairs=_pairs(
        "campo elétr campo eletr campo magnét campo magnet plano inclinado lente conv lente "
        "diverg palavras cruzadas"
    ),
    plurals=("s", "es"),
)

RUSSIAN = Topics(
    # Exact forms where a stem would also start an everyday word ("тест" / "тесто",
    # "баг" / "багаж", "идея" / "идеальный", "сила" / "силуэт", "совет" / "советский").
    _w(
        "тест теста тесты баг бага баги чат игра игру игры идея идею идеи идей речь "
        "фаза фазу фазы совет советы совета ион иона ионы сила силу силы сил цепь цепи ток "
        "днк волна волну волны волн угол угла"
    ),
    stems=_stems(
        "задани домашк напоминани проект аккаунт скрипт код файл папк заметк конспект "
        "резюме итог событи встреч опрос викторин экзамен контрольн карточк письм "
        "сообщени ответ черновик отчёт отчет компонент страниц экран кнопк пользовател "
        "парол коммит ошибк сравнени пример задач упражнени решени доказательств лайфхак "
        "секрет привычк этап музык песн плейлист приложени сайт программ рецепт стих эссе "
        "сочинени истори рассказ анекдот шутк абзац предложени введени вступлени заголов "
        "подпис биографи твит слоган запрос тренировк распорядок маршрут бюджет анкет "
        "договор контракт презентаци слайд загадк кроссворд разниц отличи урок вопрос "
        "молекул соединени реакци вектор клетк атом элемент скорост ускорени энерги "
        "парабол гипербол лучи лучей линз "
        "напряжени электрон протон нейтрон кислот изомер полимер белок белк фотосинтез "
        "митоз наклонн кофеин бензол этанол метанол аспирин глюкоз сахароз метан этан "
        "пропан бутан аммиак ацетон озон холестерин дофамин серотонин никотин парацетамол "
        "ибупрофен инсулин пенициллин морфин адреналин диоксид оксид хлорид сульфат "
        "нитрат гидроксид карбонат фенол толуол глицерин мочевин хлороформ ментол "
        "углекисл"
    ),
    pairs=_pairs("магнитн пол электрическ пол гравитационн пол"),
)

TURKISH = Topics(
    # Exact forms where a stem starts an everyday word ("fark" / "farklı", "oyun" /
    # "oyuncak", "hız" / "hızlı", "sır" / "sıra").
    _w(
        "not notu notlar notları test testi form formu oyun oyunu oyunlar sır sırrı fark "
        "farkı farkını giriş hız hızı üre dna dalga dalgayı dalgası dalgaları "
        "açı açıyı"
    ),
    stems=_stems(
        "ödev görev hatırlatı proje hesap kod dosya klasör sohbet özet etkinlik toplantı "
        "sınav quiz anket e-posta eposta mail mesaj cevap yanıt taslak rapor bileşen "
        "sayfa ekran buton düğme kullanıcı şifre parola commit hata karşılaştırma örnek "
        "problem soru alıştırma çözüm ispat kanıt ipuc ipuç alışkanlık aşama evre müzik "
        "şarkı uygulama site program tarif şiir deneme kompozisyon hikaye hikâye öykü "
        "fıkra şaka paragraf cümle başlık biyografi slogan fikir fikr sorgu antrenman "
        "rutin özgeçmiş konuşma bütçe fatura sözleşme sunum slayt bilmece bulmaca ders "
        "kuvvet bileşik tepkime reaksiyon devre vektör hücre atom element ivme enerji "
        "akım gerilim elektron proton nötron iyon asit izomer polimer protein fotosentez "
        "mitoz eğik ışın parabol mercek kafein benzen etanol metanol aspirin glikoz sakkaroz "
        "metan etan "
        "propan bütan amonyak aseton ozon kolesterol dopamin serotonin nikotin "
        "parasetamol ibuprofen insülin penisilin morfin adrenalin dioksit monoksit oksit "
        "klorür sülfat nitrat hidroksit karbonat fenol toluen gliserol kloroform mentol"
    ),
    pairs=_pairs("manyetik alan elektrik alan"),
)

AMHARIC = Topics(
    _w("ስራ ሥራ ገጽ"),
    stems=_stems(
        "ምሳሌ ችግር መፍትሄ ጥያቄ መልመጃ ማጠቃለያ ፕሮጀክት ኢሜል መልእክት ደብዳቤ ሪፖርት ድርሰት ግጥም ታሪክ ቀልድ ልዩነት ሀሳብ "
        "ሃሳብ አቀራረብ ኮድ ፈተና መተግበሪያ ጨዋታ ዘፈን አዘገጃጀት በጀት ውል ንግግር ትምህርት ኃይል ሀይል ሃይል ውህድ መዋቅር "
        "ሰርኪዩት ቬክተር ሞገድ ሴል አቶም ንጥረ ፍጥነት ኢነርጂ ኤሌክትሮን ፕሮቶን ኒውትሮን አሲድ ፕሮቲን ፎቶሲንተሲስ ካፌይን ኢታኖል "
        "አስፕሪን ግሉኮስ ሚቴን አሞኒያ ኦዞን ኮሌስትሮል ኒኮቲን ፓራሲታሞል ኢንሱሊን ዳይኦክሳይድ ኦክሳይድ"
    ),
)

TOPICS: dict[str, Topics] = {
    "es": SPANISH,
    "fr": FRENCH,
    "de": GERMAN,
    "it": ITALIAN,
    "pt": PORTUGUESE,
    "ru": RUSSIAN,
    "tr": TURKISH,
    "am": AMHARIC,
}
