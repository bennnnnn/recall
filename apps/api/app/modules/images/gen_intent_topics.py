# ruff: noqa: RUF001, RUF003 - Turkish dotless i and Cyrillic are the words matched
"""What may not be said anywhere in a picture asked in another language.

``gen_intent_drawable`` decides what a picture may be of: its head noun must be a listed
concrete thing. These lists guard the rest of the subject: "un gato con una tabla de
multiplicar", "un volcán con sus partes", "eine Blume mit ihren Teilen" have a drawable
head and are still answered in words. A subject holding one of these words draws
nothing: what English declines (``gen_intent_words.NON_IMAGE_WORDS`` and
``NON_IMAGE_DRAW_WORDS``: an example, a homework, a plan, a list, a table, a triangle, a
molecule), and the homework and figures of speech draw-me requests in these languages
turned out to hold: trajectories, forces, algorithms, cycles, parts and layers,
probabilities, decisions, family trees, "tu respuesta", "la situación", "in drei
Sätzen". Question words and negations block too ("Píntame cómo sería …").

Over-blocking is accepted: "Dibújame un perro en una tabla de surf" is answered. Words
are whole and each inflection is listed ("ejemplo(s)" is "ejemplo" and "ejemplos");
German compounds are caught by their ending ("Trainingsplan", "Säulendiagramm"), Russian
and Turkish forms by their stem ("траекторию", "tablosu"). The Amharic words are a best
effort and want a native speaker's review.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
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
    pairs: frozenset[tuple[str, str]] = frozenset()
    # German joins nouns: "Trainingsplan", "Säulendiagramm", "Einkaufsliste".
    endings: tuple[str, ...] = ()
    # Russian and Turkish inflect: "траекторию", "listesini", "tablosu".
    stems: tuple[str, ...] = ()

    def names_one(self, words: list[str]) -> bool:
        """True when ``words`` (lowercase) are about something not to draw. Each part of a
        hyphenated word counts ("Server-Backup")."""
        words = [part for word in words for part in (word, *word.split("-")) if part]
        return any(
            word in self.words
            or (self.endings and word.endswith(self.endings))
            or (self.stems and word.startswith(self.stems))
            for word in words
        ) or any(pair in self.pairs for pair in pairwise(words))


SPANISH = Topics(
    _w(
        # NON_IMAGE_WORDS: tasks, school, writing, code.
        "tarea(s) deberes recordatorio(s) proyecto(s) cuenta(s) script(s) código(s) codigo(s) "
        "función funciones funcion clase(s) archivo(s) carpeta(s) chat(s) nota(s) apunte(s) "
        "resumen resúmenes plan(es) horario(s) evento(s) reunión reuniones reunion cuestionario(s) "
        "quiz flashcard(s) correo(s) email(s) mensaje(s) borrador(es) informe(s) reporte(s) "
        "tabla(s) componente(s) página(s) pagina(s) pantalla(s) botón botones boton formulario(s) "
        "usuario(s) contraseña(s) login commit(s) bug(s) prueba(s) test(s) objeto(s) comparación "
        "comparaciones ejemplo(s) problema(s) ecuación ecuaciones ecuacion pregunta(s) "
        "ejercicio(s) solución soluciones solucion demostración demostraciones ficha(s) consejo(s) "
        "secreto(s) hábito(s) habito(s) truco(s) etapa(s) fase(s) música musica canción canciones "
        "cancion playlist(s) app(s) aplicación aplicaciones aplicacion web juego(s) programa(s) "
        "html css javascript receta(s) poema(s) ensayo(s) redacción cuento(s) chiste(s) párrafo(s) "
        "parrafo(s) frase(s) oración oraciones introducción introduccion esquema(s) biografía "
        "tuit(s) eslogan(es) idea(s) consulta(s) sql json entrenamiento(s) rutina(s) itinerario(s) "
        "currículum curriculum cv discurso(s) presupuesto(s) factura(s) encuesta(s) contrato(s) "
        "presentación presentaciones diapositiva(s) adivinanza(s) acertijo(s) crucigrama(s) "
        # NON_IMAGE_DRAW_WORDS: what the app draws itself.
        "diagrama(s) gráfica(s) grafica(s) gráfico(s) grafico(s) conclusión conclusiones "
        "conclusion inferencia(s) línea(s) linea(s) recta(s) triángulo(s) triangulo(s) cuadrado(s) "
        "círculo(s) circulo(s) rectángulo(s) rectangulo(s) trapecio(s) polígono(s) poligono(s) "
        "rombo(s) paralelogramo(s) geometría geometria hipotenusa molécula(s) molecula(s) "
        "estructura(s) química(s) quimica químico(s) curva(s) organigrama(s) cronograma(s) "
        "compuesto(s) isómero(s) adn"
    ),
    pairs=_pairs("mapa conceptual mapa mental árbol genealógico arbol genealogico de decisión"),
)

FRENCH = Topics(
    _w(
        # Not "chat": it is a cat.
        "tâche(s) devoir(s) rappel(s) projet(s) compte(s) script(s) code(s) fonction(s) classe(s) "
        "fichier(s) dossier(s) note(s) résumé(s) plan(s) planning(s) événement(s) réunion(s) quiz "
        "questionnaire(s) mail(s) email(s) courriel(s) message(s) brouillon(s) rapport(s) tableau "
        "tableaux composant(s) page(s) écran(s) bouton(s) formulaire(s) utilisateur(s) commit(s) "
        "bug(s) test(s) objet(s) comparaison(s) exemple(s) problème(s) probleme(s) équation(s) "
        "equation(s) question(s) exercice(s) solution(s) preuve(s) démonstration(s) fiche(s) "
        "conseil(s) astuce(s) secret(s) habitude(s) étape(s) phase(s) musique(s) chanson(s) "
        "playlist(s) appli(s) application(s) site(s) jeu jeux programme(s) html css javascript "
        "recette(s) poème(s) dissertation(s) rédaction(s) conte(s) blague(s) paragraphe(s) "
        "phrase(s) introduction(s) bio biographie(s) tweet(s) slogan(s) idée(s) requête(s) sql "
        "json entraînement(s) routine(s) itinéraire(s) cv discours budget(s) facture(s) sondage(s) "
        "contrat(s) présentation(s) diapositive(s) devinette(s) énigme(s) diagramme(s) "
        "graphique(s) graphe(s) courbe(s) conclusion(s) inférence(s) ligne(s) droites triangle(s) "
        "carré(s) carre(s) cercle(s) rectangle(s) trapèze(s) polygone(s) losange(s) "
        "parallélogramme(s) géométrie geometrie hypoténuse molécule(s) molecule(s) structure(s) "
        "chimie chimique(s) organigramme(s) composé(s) isomère(s) adn"
    ),
    pairs=_pairs("carte mentale arbre généalogique arbre genealogique de décision mots croisés"),
    # "(Une) droite" is a line; "un chat à droite" is on the right.
)

GERMAN = Topics(
    _w(
        "aufgabe(n) hausaufgabe(n) matheaufgabe(n) erinnerung(en) projekt(e) konto konten "
        "skript(e) code(s) funktion(en) klasse(n) datei(en) ordner chat(s) notiz(en) "
        "zusammenfassung(en) plan pläne zeitplan zeitpläne termin(e) ereignis(se) meeting(s) "
        "besprechung(en) quiz test(s) karteikarte(n) mail(s) email(s) e-mail(s) nachricht(en) "
        "entwurf entwürfe bericht(e) tabelle(n) komponente(n) bildschirm(e) button(s) knopf knöpfe "
        "formular(e) benutzer nutzer passwort passwörter commit(s) bug(s) objekt(e) vergleich(e) "
        "beispiel(e) problem(e) gleichung(en) frage(n) übung(en) lösung(en) beweis(e) arbeitsblatt "
        "arbeitsblätter tipp(s) geheimnis(se) gewohnheit(en) trick(s) phase(n) musik lied(er) "
        "song(s) playlist(s) app(s) webseite(n) website(s) spiel(e) programm(e) html css "
        "javascript rezept(e) gedicht(e) aufsatz aufsätze essay(s) witz(e) absatz absätze satz "
        "sätze einleitung(en) gliederung(en) bio tweet(s) slogan(s) idee(n) abfrage(n) sql json "
        "training workout(s) routine(n) reiseplan lebenslauf lebensläufe cv rede(n) budget(s) "
        "rechnung(en) umfrage(n) vertrag verträge präsentation(en) folie(n) rätsel kreuzworträtsel "
        "diagramm(e) schaubild(er) graph(en) kurve(n) schlussfolgerung(en) fazit linie(n) "
        "dreieck(e) quadrat(e) kreis(e) rechteck(e) trapez(e) vieleck(e) polygon(e) raute(n) "
        "parallelogramm(e) geometrie hypotenuse molekül(e) struktur(en) chemie flussdiagramm(e) "
        "mindmap(s) stammbaum stammbäume entscheidungsbaum organigramm(e) freikörperdiagramm(e) "
        "wertetabelle(n) strukturformel(n) chemisch(e|en|er|es) isomer(e) dna"
    ),
    pairs=_pairs("chemische verbindung chemischen verbindung"),
    endings=tuple(
        "diagramm diagramme diagrammen graph graphen tabelle tabellen liste listen kurve kurven "
        "gleichung gleichungen aufgabe aufgaben datenbank datenbanken plan pläne"
        "plänen zyklus kreislauf prozess routine".split()
    ),
)

ITALIAN = Topics(
    _w(
        "compito compiti promemoria progetto progetti account script codice codici funzione "
        "funzioni classe classi file cartella cartelle chat nota note appunti riassunto riassunti "
        "sintesi programma programmi evento eventi riunione riunioni quiz questionario email mail "
        "messaggio messaggi bozza bozze relazione relazioni rapporto rapporti tabella tabelle "
        "componente componenti pagina pagine schermo schermi pulsante pulsanti modulo moduli "
        "utente utenti password commit bug test oggetto oggetti confronto confronti esempio esempi "
        "problema problemi equazione equazioni domanda domande esercizio esercizi soluzione "
        "soluzioni dimostrazione dimostrazioni scheda schede consiglio consigli segreto segreti "
        "abitudine abitudini trucco trucchi fase fasi tappa tappe musica canzone canzoni playlist "
        "app applicazione applicazioni sito siti gioco giochi html css javascript ricetta ricette "
        "poesia poesie saggio saggi racconto racconti barzelletta barzellette paragrafo paragrafi "
        "frase frasi introduzione biografia tweet slogan idea idee query sql json allenamento "
        "allenamenti routine itinerario itinerari curriculum cv discorso discorsi budget bilancio "
        "fattura fatture sondaggio sondaggi contratto contratti presentazione presentazioni "
        "diapositiva diapositive slide indovinello indovinelli cruciverba diagramma diagrammi "
        "grafico grafici conclusione conclusioni linea linee retta rette triangolo triangoli "
        "quadrato quadrati cerchio cerchi rettangolo rettangoli trapezio poligono poligoni rombo "
        "parallelogramma geometria ipotenusa molecola molecole struttura strutture chimica chimico "
        "chimiche chimici curva curve organigramma composto composti isomero dna"
    ),
    pairs=_pairs(
        "mappa concettuale mappa mentale albero genealogico piano di di decisione albero "
        "decisionale"
    ),
)

PORTUGUESE = Topics(
    _w(
        "tarefa(s) dever(es) lembrete(s) projeto(s) conta(s) script(s) código(s) codigo(s) função "
        "funções funcao classe(s) arquivo(s) chat(s) nota(s) anotação anotações resumo(s) plano(s) "
        "cronograma(s) evento(s) reunião reuniões quiz questionário(s) email(s) e-mail(s) mensagem "
        "mensagens rascunho(s) relatório(s) tabela(s) componente(s) página(s) pagina(s) botão "
        "botões formulário(s) usuário(s) senha(s) commit(s) bug(s) teste(s) objeto(s) comparação "
        "comparações exemplo(s) problema(s) equação equações pergunta(s) questão questões "
        "exercício(s) exercicio(s) solução soluções solucao demonstração demonstrações ficha(s) "
        "dica(s) truque(s) segredo(s) hábito(s) etapa(s) fase(s) música(s) musica canção canções "
        "playlist(s) app(s) aplicativo(s) site(s) jogo(s) programa(s) planilha(s) html css "
        "javascript receita(s) poema(s) redação redações ensaio(s) conto(s) piada(s) parágrafo(s) "
        "frase(s) introdução biografia tweet(s) slogan(s) ideia(s) consulta(s) sql json treino(s) "
        "rotina(s) roteiro(s) currículo(s) cv discurso(s) orçamento(s) fatura(s) pesquisa(s) "
        "contrato(s) apresentação apresentações slide(s) charada(s) enigma(s) diagrama(s) "
        "gráfico(s) grafico(s) conclusão conclusões linha(s) reta(s) triângulo(s) quadrado(s) "
        "círculo(s) retângulo(s) trapézio(s) polígono(s) losango(s) paralelogramo(s) geometria "
        "hipotenusa molécula(s) molecula(s) estrutura(s) química quimica químico(s) curva(s) "
        "organograma(s) fluxograma(s) esquema(s) composto(s) isômero(s) dna"
    ),
    pairs=_pairs(
        "mapa mental mapa conceitual árvore genealógica arvore genealogica de decisão palavras "
        "cruzadas"
    ),
)

RUSSIAN = Topics(
    _w(
        "задание задания заданий домашка домашку напоминание напоминания проект проекта проекты "
        "аккаунт скрипт код кода функция функцию функции класс класса файл файла папка папку чат "
        "заметка заметку заметки конспект резюме план плана планы расписание расписания событие "
        "встреча встречу опрос викторина викторину тест теста тесты карточка карточки сообщение "
        "сообщения черновик отчёт отчет отчёта отчета таблица таблицу таблицы компонент страница "
        "страницу страницы экран кнопка кнопку кнопки пользователь пароль коммит баг объект "
        "объекта сравнение пример примера примеры уравнение уравнения вопрос вопросы упражнение "
        "упражнения решение решения доказательство совет советы секрет секреты привычка привычку "
        "этап этапы фаза фазу музыка музыку песня песню песни плейлист приложение приложения сайт "
        "игра игру игры программа программу рецепт стих стихи стихотворение эссе сочинение рассказ "
        "анекдот шутка шутку абзац предложение введение вступление подпись биография твит слоган "
        "идея идею идеи запрос тренировка тренировку распорядок маршрут речь бюджет анкета анкету "
        "договор контракт презентация презентацию слайд слайды загадка загадку кроссворд диаграмма "
        "диаграмму диаграммы схема схему график графика графики граф вывод линия линию линии "
        "прямая прямую треугольник треугольника круг круга кругу окружность окружности квадрат "
        "квадрата прямоугольник трапеция трапецию многоугольник ромб параллелограмм геометрия "
        "геометрию гипотенуза гипотенузу молекула молекулу молекулы структура структуру химия "
        "химию кривая кривую химический химическая химическое химическую химической блок-схема "
        "блок-схему интеллект-карта интеллект-карту словами изомер днк"
    ),
    pairs=_pairs("генеалогическое древо генеалогическое дерево химическое соединение"),
)

TURKISH = Topics(
    _w(
        "ödev ödevi ödevim ödevimi ödevler görev görevi hatırlatıcı hatırlatma proje projesi "
        "projem projemi hesap hesabı hesabımı kod kodu fonksiyon fonksiyonu sınıf sınıfı dosya "
        "dosyası klasör sohbet not notu notlar notları özet özeti plan planı planını takvim "
        "takvimi etkinlik toplantı test testi quiz anket e-posta eposta mail mesaj mesajı taslak "
        "rapor raporu tablo tabloyu tablolar bileşen sayfa sayfası ekran ekranı buton düğme form "
        "formu kullanıcı şifre parola commit nesne nesneyi karşılaştırma örnek örneği örnekler "
        "problem problemi soru soruyu sorular alıştırma çözüm çözümü ispat kanıt ipucu ipuçları "
        "sır sırrı alışkanlık aşama evre müzik şarkı uygulama site sitesi oyun oyunu program "
        "programı tarif tarifi şiir deneme kompozisyon hikaye hikâye öykü fıkra şaka paragraf "
        "cümle giriş biyografi slogan fikir fikri sorgu antrenman rutin özgeçmiş konuşma bütçe "
        "fatura sözleşme sunum slayt bilmece bulmaca diyagram diyagramı grafik grafiği grafiğini "
        "şema şeması şemasını sonuç sonucu çizgi çizgiyi çizgiler doğru doğruyu üçgen üçgeni kare "
        "kareyi daire daireyi çember çemberi dikdörtgen yamuk çokgen paralelkenar hipotenüs "
        "geometri molekül molekülü molekülünü yapısı yapısını kimya kimyasal eğri eğrisi "
        # "Altını çiz" underlines, "üstünü çiz" crosses out; "kedi nasıl çiz" is a question.
        "altını altlarını üstünü üzerini nasıl neden niye nedir bileşik izomer dna"
    ),
    pairs=_pairs(
        "kavram haritası kavram haritasını soy ağacı soy ağacını karar ağacı karar ağacını aile "
        "ağacı"
    ),
)

AMHARIC = Topics(
    _w(
        "ምሳሌ ምሳሌዎች ችግር ችግሩን መፍትሄ መፍትሔ ጥያቄ ጥያቄዎች መልመጃ ማጠቃለያ ፕሮጀክት ኢሜል መልእክት ሪፖርት ድርሰት ግጥም ቀልድ ሀሳብ "
        "ሃሳብ አቀራረብ ኮድ መተግበሪያ ጨዋታ ዘፈን በጀት ውል ንግግር ሰንጠረዥ ሰንጠረዡን ግራፍ ግራፉን ቻርት ዲያግራም ዝርዝር መስመር ክብ "
        "ሞለኪውል እኩልታ እቅድ ዕቅድ ቤተሰብ ክፍሎች ክፍሎቹ ካርታ ታሪክ ደብዳቤ ገበታ ንድፍ ዑደት ሂደት መዋቅር ሥርዓት ስርዓት"
    ),
    pairs=_pairs("ሶስት ማዕዘን የቤት ስራ የቤት ሥራ"),
)

# Blocked in every language: questions ("cómo sería", "wie es wäre") and negations ("nicht
# so schwarz") are no picture's subject.
_EVERY = _w(
    "qué cómo como porque pourquoi comment wie warum wieso weshalb was come perché perche cosa "
    "porquê как почему зачем что nasıl neden niçin ne ምን እንዴት ለምን nicht kein keine keinen nie pas "
    "jamais non não nao не нет никогда değil hiç asla "
    # A disk, Docker or backup image, a sheet: "Создай картинку в Excel".
    "docker iso backup excel"
)

# The families the four reviews found drawn, and what English declines that the lists
# above lacked: words, two-word pairs, Russian and Turkish stems.
_MORE: dict[str, tuple[str, str, str]] = {
    "es": (
        "medidas escenario(s) negocio(s) anatomía anatomia funcionamiento evolución tendencia(s) "
        "precio(s) teorema(s) mitosis contexto razonamiento distancia(s) no lista(s) frontera(s) "
        "trayectoria(s) fuerza(s) algoritmo(s) ciclo(s) situación situacion panorama respuesta(s) "
        "argumento(s) razón razones palabras selfie carnet documento(s) pasaporte marca empresa "
        "corporativa disco distribución vector(es) orbital(es) órbita(s) célula(s) celula(s) "
        "átomo(s) atomo(s) circuito(s) fórmula(s) formula(s) energía velocidad aceleración "
        "ángulo(s) angulo(s) parábola(s) onda(s) datos dato grados metros kilómetros diferencia(s) "
        "inflación límite(s) derivada(s) integral(es) proyectil(es) paso(s) proceso(s) "
        "fotosíntesis economía oferta demanda éxito candidato(s) organización tu tus respaldo "
        "servidor contenedor gastos camino(s) ruta(s) uñas estoy soy tengo partes capas etiquetas "
        "familiar decisiones probabilidad(es) plano(s) duda(s)",
        "",
        "",
    ),
    "fr": (
        "mesures scénario(s) anatomie récapitulatif(s) emploi frise(s) fonctionnement évolution "
        "tendance(s) prix théorème(s) mitose contexte raisonnement distance(s) liste(s) "
        "frontière(s) trajectoire(s) force(s) algorithme(s) cycle(s) situation(s) panorama "
        "réponse(s) argument(s) raison(s) mots selfie identité passeport document(s) marque "
        "entreprise disque distribution vecteur(s) orbitale(s) orbite(s) cellule(s) atome(s) "
        "circuit(s) formule(s) énergie vitesse accélération angle(s) parabole(s) onde(s) données "
        "degrés mètres différence(s) tva impôt(s) limite(s) dérivée(s) intégrale(s) projectile(s) "
        "droite schéma(s) processus photosynthèse économie offre demande succès réussite "
        "candidat(s) organisation parcours ton ta tes votre vos sauvegarde serveur conteneur "
        "dépenses aperçu chemin(s) ongles suis parties couches étiquette(s) table(s) familial "
        "décisions probabilité(s) doute(s)",
        "",
        "",
    ),
    "de": (
        "maße maßen szenario(s) geschäft anatomie zeitstrahl zeitleiste funktionsweise entwicklung "
        "trend(s) preise preis theorem kontext entfernung(en) abstand kraft kräfte kräften "
        "grenze(n) datenbank(en) liste(n) flugbahn(en) bahnkurve(n) trajektorie(n) algorithmus "
        "algorithmen zyklus zyklen kreislauf situation lage antwort(en) argument(e) gründe worten "
        "wörtern sätzen selfie ausweis reisepass dokument(e) marke firma unternehmen festplatte "
        "verteilung vektor(en) orbital(e) umlaufbahn zelle(n) zellteilung atom(e) stromkreis(e) "
        "schaltkreis(e) schaltung(en) formel(n) energie geschwindigkeit beschleunigung winkel "
        "parabel(n) welle(n) daten grad meter unterschied(e) gerade(n) grenzwert(e) ableitung(en) "
        "integral(e) schema schritt(e) schritten ablauf prozess(e) photosynthese fotosynthese "
        "mitose wirtschaft angebot nachfrage erfolg kandidat(en) organisation werdegang dein deine "
        "deinen deinem deiner deines euer eure sicherung server container ausgaben übersicht weg "
        "route zusammenhang bin teil(e|en) bestandteil(e|en) schicht(en) beschriftung(en) "
        "beschriftet(e|en|er) grundriss(e) zweifel wahrscheinlichkeit(en)",
        "",
        "",
    ),
    "it": (
        "misure scenario scenari anatomia funzionamento andamento evoluzione tendenza prezzo "
        "prezzi teorema teoremi mitosi contesto ragionamento distanza distanze no lista liste "
        "elenco elenchi confine confini frontiera frontiere database traiettoria traiettorie forza "
        "forze algoritmo algoritmi ciclo cicli situazione panorama risposta risposte "
        "argomentazione ragioni parole selfie identità passaporto documento documenti marchio "
        "azienda aziendale disco distribuzione vettore vettori orbitale orbitali orbita cellula "
        "cellule atomo atomi circuito circuiti formula formule energia velocità accelerazione "
        "angolo angoli parabola onda onde dati gradi metri differenza differenze limite derivata "
        "integrale proiettile piano piani schema schemi passo passi passaggio passaggi processo "
        "processi fotosintesi economia offerta domanda successo candidato candidati organizzazione "
        "percorso tuo tua tuoi tue vostro vostra server container spese panoramica strada sono "
        "parti strati etichette tabellina tabelline famiglia decisioni probabilità pianta "
        "piantina dubbi",
        "banca dati",
        "",
    ),
    "pt": (
        "medidas cenário(s) negócio(s) anatomia funcionamento evolução tendência(s) preço(s) "
        "teorema(s) contexto raciocínio distância(s) lista(s) fronteira(s) trajetória(s) "
        "trajetoria(s) força(s) algoritmo(s) ciclo(s) situação situacao panorama resposta(s) "
        "argumento(s) razões palavras selfie identidade passaporte documento(s) marca empresa "
        "institucional disco distribuição distribuicao vetor(es) orbital orbitais órbita(s) "
        "célula(s) celula(s) átomo(s) atomo(s) circuito(s) fórmula(s) formula(s) energia "
        "velocidade aceleração ângulo(s) angulo(s) parábola(s) onda(s) dados graus metros "
        "diferença(s) limite(s) derivada(s) integral projétil passo(s) processo(s) fotossíntese "
        "economia oferta demanda sucesso candidato(s) organização teu tua teus tuas servidor "
        "contêiner despesas gastos caminho(s) rota(s) unhas estou sou partes camadas etiquetas "
        "rótulos tabuada(s) família decisões probabilidade(s) planta dúvida(s)",
        "de dados",
        "",
    ),
    "ru": (
        "угол план плана планы планом планов сила силу силы сил силами метр метра метров цен цены "
        "ценам общую общая общий общей граница границу границы границе карта карту карты рынок я "
        "твой твою твоё твоего твоей твои твоих свой свою своё своего своей свои своих слои слоями "
        "слоёв слоев",
        "база данных базу данных базы данных",
        "спис треугольн квадрат прямоугольн окружност круги кругов линий схем диаграм график "
        "таблиц задач пример уравнен упражнен вопрос решени проект рецепт стих песен молекул "
        "структурн формул траектор алгоритм цикл "
        "ситуац ответ аргумент причин слов предложени селфи паспорт документ бренд компани диск "
        "распределени вектор орбит клетк атом цеп энерги скорост ускорен угл парабол волн данн "
        "градус разниц предел производн интеграл снаряд размер сценари распорядк бизнес анатоми "
        "шкал хронолог пирамид содержани систем функционир динамик развити тенденц теорем фаз "
        "митоз контекст будущ мысл устройств строени событ расстояни шаг процесс фотосинтез "
        "экономик спрос успех кандидат организац ваш резерв сервер обзор расход происход "
        "перспектив рынк пут част подпис семейн тьюринг теплов вероятн проблем сомнени",
    ),
    "tr": (
        "açı açısı açıyı açıları yol yolu yolunu senin sizin aile",
        "veri tabanı veri tabanını",
        "liste sınır veritaban üçgen kare daire çember dikdörtgen grafi diyagram şema tablo örnek "
        "problem soru ödev proje molekül yörünge kuvvet algoritma döngü plan formül denklem cevap "
        "durum cümle kelime vektör hücre atom devre enerji hız ivme parabol dalga dağılım derece "
        "metre fark selfie kimlik pasaport belge marka şirket disk çalış gelişim eğilim fiyat "
        "teorem evre aşama mitoz bağlam gelecek düşünce yapı genel olay mesafe limit türev "
        "integral mermi ölçü senaryo rutin anatomi çizelge program adım süreç sürec cevab örneğ "
        "kimliğ taleb fotosentez ekonomi arz talep başarı aday organizasyon yedek sunucu harcama "
        "parça katman etiket olasılık",
    ),
    "am": ("ድንበር ዳታቤዝ ቀመር ስሌት ሕዋስ አቶም ኃይል ኃይሎች ሀይል መልስ መልሱን", "", ""),
}  # fmt: skip


def _with_more(code: str, topics: Topics) -> Topics:
    words, pairs, stems = _MORE[code]
    listed = topics.words | _w(words)
    if code == "am":
        # "የቤተሰብ ዛፍ" (the family's tree): Amharic writes "of" as the noun's first letter.
        listed |= {f"የ{word}" for word in listed}
    return replace(
        topics,
        words=listed | _EVERY,
        pairs=topics.pairs | (_pairs(pairs) if pairs else frozenset()),
        stems=tuple(stems.split()),
    )


TOPICS: dict[str, Topics] = {
    code: _with_more(code, topics)
    for code, topics in (
        ("es", SPANISH),
        ("fr", FRENCH),
        ("de", GERMAN),
        ("it", ITALIAN),
        ("pt", PORTUGUESE),
        ("ru", RUSSIAN),
        ("tr", TURKISH),
        ("am", AMHARIC),
    )
}
