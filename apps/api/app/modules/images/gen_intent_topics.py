# ruff: noqa: RUF001, RUF003 - Turkish dotless i and Cyrillic are the words matched
"""What a picture request in another language may not be about: exactly what English
declines.

A request routes as its English translation does on main. English draws nothing for a
subject holding one of ``gen_intent_words.NON_IMAGE_WORDS`` or ``NON_IMAGE_DRAW_WORDS``
("draw an example", "draw a table", "draw a triangle", "draw a molecule"), and hands a
named compound ("draw caffeine") or the forces on a body on a slope to chemistry and
physics (``stem_subject_claims``). These are those words' translations, whole words only,
each inflection listed ("ejemplo(s)" is "ejemplo" and "ejemplos"): "Нарисуй белку" is a
squirrel, "Musiker" a musician, "çizgi film" a cartoon. Whatever English draws ("draw an
atom", "a sine wave", "a circuit", "the electric field of a dipole", "an exam") draws here.

A word with two senses keeps its picture sense where the next word says so ("bouton de
rose", "hesap makinesi", "çizgi film"). Forces count only beside a slope ("the forces on a
block on an incline" is physics; "the forces acting on a car" is a picture). The Amharic
words are a best effort and want a native speaker's review.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from itertools import pairwise

_FORMS = re.compile(r"^([^()]+)\(([^()]+)\)$")


def _w(words: str) -> frozenset[str]:
    """ "ejemplo(s) solución" -> ejemplo, ejemplos, solución."""
    out: set[str] = set()
    for word in words.split():
        match = _FORMS.match(word)
        if match is None:
            out.add(word)
            continue
        stem, endings = match.groups()
        out.add(stem)
        out.update(stem + ending for ending in endings.split("|"))
    return frozenset(out)


def _pairs(words: str) -> frozenset[tuple[str, str]]:
    """ "mapa conceptual árbol genealógico": two neighbouring words, two by two."""
    split = words.split()
    return frozenset(zip(split[::2], split[1::2], strict=True))


@dataclass(frozen=True)
class Topics:
    words: frozenset[str]
    pairs: frozenset[tuple[str, str]] = field(default_factory=frozenset)
    # The word keeps its picture sense before this one ("bouton de rose").
    allowed: frozenset[tuple[str, str]] = field(default_factory=frozenset)
    forces: frozenset[str] = frozenset()
    slopes: frozenset[str] = frozenset()
    # A topic only as the thing drawn: "(eine) Gerade" is a line, "die gerade schläft" not.
    leading: frozenset[str] = frozenset()
    determiners: frozenset[str] = frozenset()

    def names_one(self, words: list[str]) -> bool:
        """True when ``words`` (lowercase) are about something English draws nothing for."""
        head = words[1:2] if words[:1] and words[0] in self.determiners else words[:1]
        if head and head[0] in self.leading:
            return True
        for index, word in enumerate(words):
            following = words[index + 1] if index + 1 < len(words) else ""
            if word in self.words and (word, following) not in self.allowed:
                return True
        if any(pair in self.pairs for pair in pairwise(words)):
            return True
        found = set(words)
        return bool(found & self.forces) and bool(found & self.slopes)


SPANISH = Topics(
    _w(
        # NON_IMAGE_WORDS: tasks, school, writing, code.
        "tarea(s) deberes recordatorio(s) proyecto(s) cuenta(s) script(s) código(s) "
        "codigo(s) función funciones funcion clase(s) archivo(s) carpeta(s) chat(s) nota(s) "
        "apunte(s) resumen resúmenes plan(es) horario(s) evento(s) reunión reuniones reunion "
        "cuestionario(s) quiz flashcard(s) correo(s) email(s) mensaje(s) borrador(es) "
        "informe(s) reporte(s) tabla(s) componente(s) página(s) pagina(s) pantalla(s) botón "
        "botones boton formulario(s) usuario(s) contraseña(s) login commit(s) bug(s) "
        "prueba(s) test(s) objeto(s) comparación comparaciones ejemplo(s) problema(s) "
        "ecuación ecuaciones ecuacion pregunta(s) ejercicio(s) solución soluciones solucion "
        "demostración demostraciones ficha(s) consejo(s) secreto(s) hábito(s) habito(s) "
        "truco(s) etapa(s) fase(s) música musica canción canciones cancion playlist(s) "
        "app(s) aplicación aplicaciones aplicacion web juego(s) programa(s) html css "
        "javascript receta(s) poema(s) ensayo(s) redacción cuento(s) chiste(s) párrafo(s) "
        "parrafo(s) frase(s) oración oraciones introducción introduccion esquema(s) "
        "biografía tuit(s) eslogan(es) idea(s) consulta(s) sql json entrenamiento(s) "
        "rutina(s) itinerario(s) currículum curriculum cv discurso(s) presupuesto(s) "
        "factura(s) encuesta(s) contrato(s) presentación presentaciones diapositiva(s) "
        "adivinanza(s) acertijo(s) crucigrama(s) "
        # NON_IMAGE_DRAW_WORDS: what the app draws itself.
        "diagrama(s) gráfica(s) grafica(s) gráfico(s) grafico(s) conclusión conclusiones "
        "conclusion inferencia(s) línea(s) linea(s) recta(s) triángulo(s) triangulo(s) "
        "cuadrado(s) círculo(s) circulo(s) rectángulo(s) rectangulo(s) trapecio(s) "
        "polígono(s) poligono(s) rombo(s) paralelogramo(s) geometría geometria hipotenusa "
        "molécula(s) molecula(s) estructura(s) química(s) quimica químico(s) curva(s) "
        "organigrama(s) cronograma(s) "
        # Chemistry by name.
        "compuesto(s) isómero(s) adn cafeína cafeina benceno etanol metanol aspirina glucosa "
        "sacarosa metano etano propano butano amoníaco amoniaco acetona ozono colesterol "
        "dopamina serotonina nicotina paracetamol ibuprofeno insulina penicilina morfina "
        "adrenalina dióxido monóxido óxido oxido cloruro sulfato nitrato hidróxido carbonato "
        "fenol tolueno glicerol urea formaldehído cloroformo mentol"
    ),
    pairs=_pairs(
        "mapa conceptual mapa mental árbol genealógico arbol genealogico de decisión "
        "ácido acético ácido sulfúrico ácido clorhídrico ácido nítrico acido acetico"
    ),
    allowed=_pairs("botón de"),
    forces=_w("fuerza(s)"),
    slopes=_w("inclinado inclinada rampa pendiente"),
)

FRENCH = Topics(
    _w(
        # Not "chat": it is a cat.
        "tâche(s) devoir(s) rappel(s) projet(s) compte(s) script(s) code(s) fonction(s) "
        "classe(s) fichier(s) dossier(s) note(s) résumé(s) plan(s) planning(s) événement(s) "
        "réunion(s) quiz questionnaire(s) mail(s) email(s) courriel(s) message(s) "
        "brouillon(s) rapport(s) tableau tableaux composant(s) page(s) écran(s) bouton(s) "
        "formulaire(s) utilisateur(s) commit(s) bug(s) test(s) objet(s) comparaison(s) "
        "exemple(s) problème(s) probleme(s) équation(s) equation(s) question(s) exercice(s) "
        "solution(s) preuve(s) démonstration(s) fiche(s) conseil(s) astuce(s) secret(s) "
        "habitude(s) étape(s) phase(s) musique(s) chanson(s) playlist(s) appli(s) "
        "application(s) site(s) jeu jeux programme(s) html css javascript recette(s) "
        "poème(s) dissertation(s) rédaction(s) conte(s) blague(s) paragraphe(s) phrase(s) "
        "introduction(s) bio biographie(s) tweet(s) slogan(s) idée(s) requête(s) sql json "
        "entraînement(s) routine(s) itinéraire(s) cv discours budget(s) facture(s) "
        "sondage(s) contrat(s) présentation(s) diapositive(s) devinette(s) énigme(s) "
        "diagramme(s) graphique(s) graphe(s) courbe(s) conclusion(s) inférence(s) ligne(s) "
        "droites triangle(s) carré(s) carre(s) cercle(s) rectangle(s) trapèze(s) polygone(s) "
        "losange(s) parallélogramme(s) géométrie geometrie hypoténuse molécule(s) "
        "molecule(s) structure(s) chimie chimique(s) organigramme(s) "
        "composé(s) isomère(s) adn caféine benzène éthanol méthanol aspirine glucose "
        "saccharose méthane éthane propane butane ammoniac acétone ozone cholestérol "
        "dopamine sérotonine nicotine paracétamol ibuprofène insuline pénicilline morphine "
        "adrénaline dioxyde monoxyde oxyde chlorure sulfate nitrate hydroxyde carbonate "
        "phénol toluène glycérol urée chloroforme menthol"
    ),
    pairs=_pairs(
        "carte mentale arbre généalogique arbre genealogique de décision mots "
        "croisés acide acétique acide sulfurique acide chlorhydrique acide nitrique"
    ),
    # "(Une) droite" is a line; "un chat à droite" is on the right.
    leading=_w("droite"),
    determiners=_w("la le l' une"),
    allowed=_pairs("bouton de bouton d'"),
    forces=_w("force(s)"),
    slopes=_w("incliné inclinée rampe pente"),
)

GERMAN = Topics(
    _w(
        "aufgabe(n) hausaufgabe(n) matheaufgabe(n) erinnerung(en) projekt(e) konto konten "
        "skript(e) code(s) funktion(en) klasse(n) datei(en) ordner chat(s) notiz(en) "
        "zusammenfassung(en) plan pläne zeitplan zeitpläne termin(e) ereignis(se) "
        "meeting(s) besprechung(en) quiz test(s) karteikarte(n) mail(s) email(s) e-mail(s) "
        "nachricht(en) entwurf entwürfe bericht(e) tabelle(n) komponente(n) bildschirm(e) "
        "button(s) knopf knöpfe formular(e) benutzer nutzer passwort passwörter commit(s) "
        "bug(s) objekt(e) vergleich(e) beispiel(e) problem(e) gleichung(en) frage(n) "
        "übung(en) lösung(en) beweis(e) arbeitsblatt arbeitsblätter tipp(s) geheimnis(se) "
        "gewohnheit(en) trick(s) phase(n) musik lied(er) song(s) playlist(s) app(s) "
        "webseite(n) website(s) spiel(e) programm(e) html css javascript rezept(e) "
        "gedicht(e) aufsatz aufsätze essay(s) witz(e) absatz absätze satz sätze "
        "einleitung(en) gliederung(en) bio tweet(s) slogan(s) idee(n) abfrage(n) sql json "
        "training workout(s) routine(n) reiseplan lebenslauf lebensläufe cv rede(n) "
        "budget(s) rechnung(en) umfrage(n) vertrag verträge präsentation(en) folie(n) "
        "rätsel kreuzworträtsel "
        "diagramm(e) schaubild(er) graph(en) kurve(n) schlussfolgerung(en) fazit linie(n) "
        "dreieck(e) quadrat(e) kreis(e) rechteck(e) trapez(e) vieleck(e) polygon(e) "
        "raute(n) parallelogramm(e) geometrie hypotenuse molekül(e) struktur(en) chemie "
        "flussdiagramm(e) mindmap(s) stammbaum stammbäume entscheidungsbaum organigramm(e) "
        "freikörperdiagramm(e) wertetabelle(n) strukturformel(n) chemisch(e|en|er|es) "
        "isomer(e) dna koffein coffein benzol ethanol methanol aspirin glukose glucose "
        "saccharose methan ethan propan butan ammoniak aceton ozon cholesterin dopamin "
        "serotonin nikotin paracetamol ibuprofen insulin penicillin morphin adrenalin "
        "kohlendioxid kohlenmonoxid natriumchlorid eisenoxid phenol toluol glycerin "
        "harnstoff chloroform menthol essigsäure schwefelsäure salzsäure salpetersäure"
    ),
    pairs=_pairs("chemische verbindung chemischen verbindung"),
    # "(Eine) Gerade" is a line; "eine Katze, die gerade schläft" is right now.
    leading=_w("gerade geraden"),
    determiners=_w("die eine zwei"),
    forces=_w("kraft kräfte"),
    slopes=_w("schiefe schiefen rampe hang abhang"),
)

ITALIAN = Topics(
    _w(
        "compito compiti promemoria progetto progetti account script codice codici funzione "
        "funzioni classe classi file cartella cartelle chat nota note appunti riassunto "
        "riassunti sintesi programma programmi evento eventi riunione riunioni quiz "
        "questionario email mail messaggio messaggi bozza bozze relazione relazioni "
        "rapporto rapporti tabella tabelle componente componenti pagina pagine schermo "
        "schermi pulsante pulsanti modulo moduli utente utenti password commit bug test "
        "oggetto oggetti confronto confronti esempio esempi problema problemi equazione "
        "equazioni domanda domande esercizio esercizi soluzione soluzioni dimostrazione "
        "dimostrazioni scheda schede consiglio consigli segreto segreti abitudine abitudini "
        "trucco trucchi fase fasi tappa tappe musica canzone canzoni playlist app "
        "applicazione applicazioni sito siti gioco giochi html css javascript ricetta "
        "ricette poesia poesie saggio saggi racconto racconti barzelletta barzellette "
        "paragrafo paragrafi frase frasi introduzione biografia tweet slogan idea idee "
        "query sql json allenamento allenamenti routine itinerario itinerari curriculum cv "
        "discorso discorsi budget bilancio fattura fatture sondaggio sondaggi contratto "
        "contratti presentazione presentazioni diapositiva diapositive slide indovinello "
        "indovinelli cruciverba "
        "diagramma diagrammi grafico grafici conclusione conclusioni linea linee retta rette "
        "triangolo triangoli quadrato quadrati cerchio cerchi rettangolo rettangoli trapezio "
        "poligono poligoni rombo parallelogramma geometria ipotenusa molecola molecole "
        "struttura strutture chimica chimico chimiche chimici curva curve organigramma "
        "composto composti isomero dna caffeina benzene etanolo metanolo aspirina glucosio "
        "saccarosio metano etano propano butano ammoniaca acetone ozono colesterolo dopamina "
        "serotonina nicotina paracetamolo ibuprofene insulina penicillina morfina "
        "adrenalina anidride biossido ossido cloruro solfato nitrato idrossido carbonato "
        "fenolo toluene glicerolo urea cloroformio mentolo"
    ),
    pairs=_pairs(
        "mappa concettuale mappa mentale albero genealogico piano di di decisione acido "
        "acetico acido solforico acido cloridrico acido nitrico"
    ),
    forces=_w("forza forze"),
    slopes=_w("inclinato inclinata rampa pendio pendenza"),
)

PORTUGUESE = Topics(
    _w(
        "tarefa(s) dever(es) lembrete(s) projeto(s) conta(s) script(s) código(s) codigo(s) "
        "função funções funcao classe(s) arquivo(s) chat(s) nota(s) anotação anotações "
        "resumo(s) plano(s) cronograma(s) evento(s) reunião reuniões quiz questionário(s) "
        "email(s) e-mail(s) mensagem mensagens rascunho(s) relatório(s) tabela(s) "
        "componente(s) página(s) pagina(s) tela(s) botão botões formulário(s) usuário(s) "
        "senha(s) commit(s) bug(s) teste(s) objeto(s) comparação comparações exemplo(s) "
        "problema(s) equação equações pergunta(s) questão questões exercício(s) "
        "exercicio(s) solução soluções solucao demonstração demonstrações ficha(s) dica(s) "
        "truque(s) segredo(s) hábito(s) etapa(s) fase(s) música(s) musica canção canções "
        "playlist(s) app(s) aplicativo(s) site(s) jogo(s) programa(s) planilha(s) html css "
        "javascript receita(s) poema(s) redação redações ensaio(s) conto(s) piada(s) "
        "parágrafo(s) frase(s) introdução biografia tweet(s) slogan(s) ideia(s) consulta(s) "
        "sql json treino(s) rotina(s) roteiro(s) currículo(s) cv discurso(s) orçamento(s) "
        "fatura(s) pesquisa(s) contrato(s) apresentação apresentações slide(s) charada(s) "
        "enigma(s) "
        "diagrama(s) gráfico(s) grafico(s) conclusão conclusões linha(s) reta(s) "
        "triângulo(s) quadrado(s) círculo(s) retângulo(s) trapézio(s) polígono(s) "
        "losango(s) paralelogramo(s) geometria hipotenusa molécula(s) molecula(s) "
        "estrutura(s) química quimica químico(s) curva(s) organograma(s) fluxograma(s) "
        "esquema(s) "
        "composto(s) isômero(s) dna cafeína cafeina benzeno etanol metanol aspirina glicose "
        "sacarose metano etano propano butano amônia amonia amoníaco acetona ozônio "
        "colesterol dopamina serotonina nicotina paracetamol ibuprofeno insulina penicilina "
        "morfina adrenalina dióxido monóxido óxido cloreto sulfato nitrato hidróxido "
        "carbonato fenol tolueno glicerol ureia clorofórmio mentol"
    ),
    pairs=_pairs(
        "mapa mental mapa conceitual árvore genealógica arvore genealogica de decisão "
        "palavras cruzadas ácido acético ácido sulfúrico ácido clorídrico ácido nítrico"
    ),
    allowed=_pairs("botão de"),
    forces=_w("força(s)"),
    slopes=_w("inclinado inclinada rampa ladeira declive"),
)

RUSSIAN = Topics(
    _w(
        "задание задания заданий домашка домашку напоминание напоминания проект проекта "
        "проекты аккаунт скрипт код кода функция функцию функции класс класса файл файла "
        "папка папку чат заметка заметку заметки конспект резюме план плана планы "
        "расписание расписания событие встреча встречу опрос викторина викторину тест теста "
        "тесты карточка карточки сообщение сообщения черновик отчёт отчет отчёта отчета "
        "таблица таблицу таблицы компонент страница страницу страницы экран кнопка кнопку "
        "кнопки пользователь пароль коммит баг объект объекта сравнение пример примера "
        "примеры уравнение уравнения вопрос вопросы упражнение упражнения решение решения "
        "доказательство совет советы секрет секреты привычка привычку этап этапы фаза фазу "
        "музыка музыку песня песню песни плейлист приложение приложения сайт игра игру игры "
        "программа программу рецепт стих стихи стихотворение эссе сочинение рассказ анекдот "
        "шутка шутку абзац предложение введение вступление подпись биография твит слоган "
        "идея идею идеи запрос тренировка тренировку распорядок маршрут речь бюджет анкета "
        "анкету договор контракт презентация презентацию слайд слайды загадка загадку "
        "кроссворд "
        "диаграмма диаграмму диаграммы схема схему график графика графики граф графа вывод "
        "линия линию линии прямая прямую треугольник треугольника круг круга кругу "
        "окружность окружности квадрат квадрата прямоугольник трапеция трапецию "
        "многоугольник ромб параллелограмм геометрия геометрию гипотенуза гипотенузу "
        "молекула молекулу молекулы структура структуру химия химию кривая кривую "
        "химический химическая химическое химическую химической "
        "блок-схема блок-схему интеллект-карта интеллект-карту словами "
        "изомер днк кофеин бензол этанол метанол аспирин глюкоза глюкозу сахароза сахарозу "
        "метан этан пропан бутан аммиак ацетон озон холестерин дофамин серотонин никотин "
        "парацетамол ибупрофен инсулин пенициллин морфин адреналин диоксид оксид хлорид "
        "сульфат нитрат гидроксид карбонат фенол толуол глицерин мочевина мочевину "
        "хлороформ ментол"
    ),
    pairs=_pairs(
        "генеалогическое древо генеалогическое дерево химическое соединение уксусная "
        "кислота уксусную кислоту серная кислота серную кислоту соляная кислота соляную "
        "кислоту углекислый газ"
    ),
    forces=_w("сила силу силы сил"),
    slopes=_w("наклонной наклонная наклонную горке склоне склону"),
)

TURKISH = Topics(
    _w(
        "ödev ödevi ödevim ödevimi ödevler görev görevi hatırlatıcı hatırlatma proje "
        "projesi projem projemi hesap hesabı hesabımı kod kodu fonksiyon fonksiyonu sınıf "
        "sınıfı dosya dosyası klasör sohbet not notu notlar notları özet özeti plan planı "
        "planını takvim takvimi etkinlik toplantı test testi quiz anket e-posta eposta mail "
        "mesaj mesajı taslak rapor raporu tablo tabloyu tablolar bileşen sayfa sayfası "
        "ekran ekranı buton düğme form formu kullanıcı şifre parola commit nesne nesneyi "
        "karşılaştırma örnek örneği örnekler problem problemi soru soruyu sorular alıştırma "
        "çözüm çözümü ispat kanıt ipucu ipuçları sır sırrı alışkanlık aşama evre müzik "
        "şarkı uygulama site sitesi oyun oyunu program programı tarif tarifi şiir deneme "
        "kompozisyon hikaye hikâye öykü fıkra şaka paragraf cümle giriş biyografi slogan "
        "fikir fikri sorgu antrenman rutin özgeçmiş konuşma bütçe fatura sözleşme sunum "
        "slayt bilmece bulmaca "
        "diyagram diyagramı grafik grafiği grafiğini şema şeması şemasını sonuç sonucu "
        "çizgi çizgiyi çizgiler doğru doğruyu üçgen üçgeni kare kareyi daire daireyi çember "
        "çemberi dikdörtgen yamuk çokgen paralelkenar hipotenüs geometri molekül molekülü "
        "molekülünü yapısı yapısını kimya kimyasal eğri eğrisi "
        # "Altını çiz" underlines, "üstünü çiz" crosses out; "kedi nasıl çiz" is a question.
        "altını altlarını üstünü üzerini nasıl neden niye nedir "
        "bileşik izomer dna kafein kafeini benzen benzeni etanol etanolü metanol aspirin "
        "aspirini glikoz glikozu sakkaroz metan metanı etan propan bütan amonyak amonyağı "
        "aseton ozon kolesterol dopamin serotonin nikotin parasetamol ibuprofen insülin "
        "penisilin morfin adrenalin dioksit monoksit oksit klorür sülfat nitrat hidroksit "
        "karbonat fenol toluen gliserol üre kloroform mentol"
    ),
    pairs=_pairs(
        "kavram haritası kavram haritasını soy ağacı soy ağacını karar ağacı karar ağacını "
        "asetik asit sülfürik asit karbon dioksit"
    ),
    allowed=_pairs("çizgi film çizgi filmi çizgi roman hesap makinesi"),
    forces=_w("kuvvet kuvveti kuvvetler kuvvetleri"),
    slopes=_w("eğik eğimli rampa rampada yokuş yokuşta"),
)

AMHARIC = Topics(
    _w(
        "ምሳሌ ምሳሌዎች ችግር ችግሩን መፍትሄ መፍትሔ ጥያቄ ጥያቄዎች መልመጃ ማጠቃለያ ፕሮጀክት ኢሜል መልእክት "
        "ሪፖርት ድርሰት ግጥም ቀልድ ሀሳብ ሃሳብ አቀራረብ ኮድ መተግበሪያ ጨዋታ ዘፈን በጀት ውል ንግግር "
        "ሰንጠረዥ ሰንጠረዡን ግራፍ ግራፉን ቻርት ዲያግራም ዝርዝር መስመር ክብ ሞለኪውል እኩልታ እቅድ "
        "ካፌይን ኢታኖል አስፕሪን ግሉኮስ ሚቴን አሞኒያ ኦዞን ኮሌስትሮል ኒኮቲን ፓራሲታሞል ኢንሱሊን "
        "ዳይኦክሳይድ ኦክሳይድ"
    ),
    pairs=_pairs("ሶስት ማዕዘን የቤት ስራ የቤት ሥራ"),
    forces=_w("ኃይል ኃይሎች ሀይል"),
    slopes=_w("ተዳፋት"),
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
