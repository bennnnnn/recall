"""The behavior battery: prompts a real user sends, and how Recall should handle each.

One list feeds two runs:

- ``test_battery.py`` (CI) sends every prompt through the real turn routing with
  external services stubbed and checks the ``Expect`` fields.
- ``scripts/battery.py`` (``./scripts/dev.sh battery``) sends the same prompts to a
  running API and writes the replies, photos and sources to one report.

``gap`` names something Recall should do and does not yet. Its routing check is an
expected failure until the gap is fixed; then the check passes, the test says so, and
the ``gap`` line comes out. ``good`` says what a good reply looks like, for whoever
reads the replay report.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Search = Literal["yes", "ask", "no"]
"""``yes``: searched with no model asked. ``ask``: a model decides. ``no``: no search."""

CATEGORIES = (
    "math",
    "physics",
    "chemistry",
    "web search",
    "photos and maps",
    "time and location",
    "teaching",
    "format",
    "code",
    "tone and emoji",
    "personal",
)


@dataclass(frozen=True)
class Expect:
    """What routing must do. ``None`` (or an empty tuple) leaves a signal unchecked."""

    search: Search | None = None
    # The reference-photo search the turn runs; "" means no photo lookup.
    photo: str | None = None
    # Words the photo search must not carry ("new": find the model's name first).
    photo_not: tuple[str, ...] = ()
    image_gen: bool | None = None
    # "math" / "physics" / "chemistry", or "" for none.
    subject: str | None = None
    # A solver checked the answer before the model wrote it.
    solved: bool | None = None
    # "clock", "location", "solver" or "" for a model-written reply.
    instant: str | None = None
    lightweight: bool | None = None
    # Prompt hints that must be present / absent (names from harness.HINTS).
    hints: tuple[str, ...] = ()
    no_hints: tuple[str, ...] = ()
    # A real photo above the model's answer (it opened with ```photo). Routing can
    # only check the hint that offers it; the live replay checks the photo.
    answer_photo: bool | None = None


@dataclass(frozen=True)
class Case:
    id: str
    category: str
    prompt: str
    expect: Expect
    good: str
    gap: str | None = None
    # Earlier turns as (role, text), oldest first.
    history: tuple[tuple[str, str], ...] = ()
    pro: bool = False
    location: str | None = None
    tags: tuple[str, ...] = field(default=())


NO_PHOTO = ""
NONE = ""

CASES: tuple[Case, ...] = (
    # ── Math ────────────────────────────────────────────────────────────────
    Case(
        "math-linear",
        "math",
        "solve 2x + 5 = 17",
        Expect(subject="math", solved=True, photo=NO_PHOTO),
        "x = 6, with the two steps shown.",
    ),
    Case(
        "math-do-it-after-word-problem",
        "math",
        "Do it",
        Expect(solved=False, instant=""),
        "Works the sled problem it just set: a = 4 m/s², v = 12 m/s, s = 18 m. Never a "
        "verified 'no solution' for the F = ma in its hint.",
        history=(
            ("user", "Give me a problem"),
            (
                "assistant",
                "**Problem:** A 5 kg sled is pulled across a frictionless ice surface by a "
                "horizontal rope that exerts a constant force of 20 N. The sled starts from "
                "rest.\n\n1. Find the sled's acceleration.\n2. Determine its speed after 3 "
                "seconds.\n3. Compute the distance it travels in those 3 seconds.\n\n*Hint:* "
                "Use $F = ma$ for (a), $v = at$ for (b), and $s = \\frac12 a t^2$ for (c).",
            ),
        ),
    ),
    Case(
        "math-derivative",
        "math",
        "what is the derivative of x^3 sin x",
        Expect(subject="math", solved=True),
        "3x² sin x + x³ cos x by the product rule.",
    ),
    Case(
        "math-integral",
        "math",
        "integrate x e^x dx",
        Expect(subject="math", solved=True),
        "(x − 1)eˣ + C by parts.",
    ),
    Case(
        "math-graph",
        "math",
        "graph y = x^2 - 4x + 3",
        Expect(subject="math", photo=NO_PHOTO),
        "A graph of the parabola with roots 1 and 3 and vertex (2, −1).",
    ),
    Case(
        "math-percent",
        "math",
        "what is 15% of 240",
        Expect(subject="math", search="no"),
        "36.",
    ),
    Case(
        "math-check-work",
        "math",
        "I got x = 4 for 3x - 2 = 10, is that right?",
        Expect(subject="math", solved=True, search="no"),
        "Yes: 3·4 − 2 = 10.",
    ),
    Case(
        "math-word-problem",
        "math",
        "A train travels 120 km in 1.5 hours. What is its average speed?",
        Expect(search="no", photo=NO_PHOTO),
        "80 km/h.",
    ),
    Case(
        "math-proportion-recipe",
        "math",
        "A recipe needs 3 cups of flour for 12 cookies. How many cups for 30 cookies?",
        Expect(subject="math", solved=True, search="no", no_hints=("advice",)),
        "7.5 cups (3/12 of a cup per cookie, times 30). A proportion, not a recipe pick.",
    ),
    Case(
        "math-triangle-area",
        "math",
        "a triangle has sides 3, 4 and 5. what is its area?",
        Expect(subject="math", search="no"),
        "6 square units (a right triangle, ½·3·4).",
    ),
    Case(
        "math-vertex",
        "math",
        "find the vertex of y = x^2 - 6x + 5",
        Expect(subject="math", solved=True, instant="solver", search="no"),
        "(3, −4), from h = −b/2a. Never the equation solved for x.",
    ),
    Case(
        "math-line-through-point",
        "math",
        "find the equation of the line parallel to y = 3x + 1 through (2, 5)",
        Expect(subject="math", solved=True, search="no"),
        "y = 3x − 1: the same slope 3, through (2, 5).",
    ),
    Case(
        "math-claimed-answer",
        "math",
        "check my answer: x = 6",
        Expect(subject="math", solved=True, search="no"),
        "Not quite: 4(6) − 7 = 17, not 21. The answer is x = 7. Never a ✓ for x = 6.",
        history=(("user", "Solve 4x - 7 = 21"), ("assistant", "```answer\nx = 7\n```")),
    ),
    Case(
        "math-bare-claim",
        "math",
        "x = 6",
        Expect(solved=False, instant=""),
        "Asks what x = 6 is the answer to. Never a verified card that only repeats it.",
    ),
    Case(
        "math-simplify-it",
        "math",
        "simplify it",
        # The message alone is not maths; the thread supplies the expression.
        Expect(solved=True, search="no"),
        "x + 1, from the rational expression the user sent. Never the product i·t.",
        history=(("user", "(x^2-1)/(x-1)"), ("assistant", "That is a rational expression in x.")),
    ),
    Case(
        "math-restated-equation",
        "math",
        "what about 2x + 5 = 21",
        # The lead kept the equation from reading as maths at all.
        Expect(solved=True, instant="solver", search="no"),
        "x = 8, worked the same way as the last equation.",
        history=(
            ("user", "solve 2x + 5 = 17"),
            ("assistant", "```answer\nverified: true\nx = 6\n```"),
        ),
    ),
    Case(
        "math-percent-thousands",
        "math",
        "what is 20% of 1,000",
        Expect(subject="math", solved=True, search="no"),
        "200. The comma groups the thousands.",
    ),
    Case(
        "math-divide-by-zero",
        "math",
        "what is 5/0",
        Expect(subject="math", solved=True, search="no"),
        "Undefined: nothing times 0 makes 5. Never NaN or complex infinity.",
    ),
    Case(
        "math-lookalike-differentiate",
        "math",
        "differentiate between weather and climate",
        Expect(subject="", solved=False),
        "Weather is the short term, climate the long-term pattern. Not maths.",
    ),
    # ── Physics ─────────────────────────────────────────────────────────────
    Case(
        "physics-drop",
        "physics",
        "a ball is dropped from 20 m. how long until it hits the ground?",
        Expect(subject="physics", solved=True, search="no"),
        "About 2.02 s from t = √(2h/g).",
    ),
    Case(
        "physics-force",
        "physics",
        "what force is needed to accelerate a 10 kg mass at 3 m/s^2?",
        Expect(subject="physics", solved=True),
        "30 N from F = ma.",
    ),
    Case(
        "physics-ohm",
        "physics",
        "a 12 V battery is connected to a 4 ohm resistor. what is the current?",
        Expect(subject="physics", solved=True),
        "3 A from I = V/R.",
    ),
    Case(
        "physics-concept",
        "physics",
        "explain Newton's third law",
        Expect(search="no", solved=False, photo=NO_PHOTO),
        "Equal and opposite forces on two different bodies, with an everyday example.",
    ),
    Case(
        "physics-followup-how-far",
        "physics",
        "how far does it go?",
        # The car, not the user: never "I don't have your location".
        Expect(solved=True, instant="", search="no"),
        "37.5 m from s = ½at², the same car and numbers.",
        history=(
            ("user", "A car accelerates from rest at 3 m/s^2 for 5 s. What is its final velocity?"),
            ("assistant", "**Answer**\n\n```answer\nverified: true\n15\\,\\mathrm{m/s}\n```"),
        ),
    ),
    Case(
        "physics-followup-unit",
        "physics",
        "in km/h please",
        Expect(solved=True, instant="", search="no"),
        "54 km/h: the verified 15 m/s converted, never worked again unchecked.",
        history=(
            ("user", "A car accelerates from rest at 3 m/s^2 for 5 s. What is its final velocity?"),
            ("assistant", "**Answer**\n\n```answer\nverified: true\n15\\,\\mathrm{m/s}\n```"),
        ),
    ),
    Case(
        "physics-followup-new-time",
        "physics",
        "and after 10 s?",
        Expect(solved=True, instant="", search="no"),
        "30 m/s: the same car after 10 s.",
        history=(
            ("user", "A car accelerates from rest at 3 m/s^2 for 5 s. What is its final velocity?"),
            ("assistant", "**Answer**\n\n```answer\nverified: true\n15\\,\\mathrm{m/s}\n```"),
        ),
    ),
    Case(
        "physics-unverified-self-check",
        "physics",
        "Two 6 ohm resistors in parallel are in series with a 3 ohm resistor across a 12 V "
        "battery. Find the current from the battery.",
        # Series-parallel networks stay with the model: it uses the same layout and
        # checks its own answer, since no server check stands behind it.
        Expect(subject="physics", solved=False, hints=("self_check",)),
        "Given/Find/Formula/Substitution/Answer: R = 3 + 3 = 6 Ω, I = 12/6 = 2 A, then a "
        "one-line Check. Never a ✓ and never 'verified'.",
    ),
    Case(
        "physics-verified-no-self-check",
        "physics",
        "a ball is dropped from 45 m. how long until it hits the ground?",
        Expect(subject="physics", solved=True, no_hints=("self_check",)),
        "About 3.03 s from t = √(2h/g), copied from the verified card.",
    ),
    # ── Chemistry ───────────────────────────────────────────────────────────
    Case(
        "chem-balance",
        "chemistry",
        "balance H2 + O2 -> H2O",
        Expect(subject="chemistry", search="no"),
        "2H₂ + O₂ → 2H₂O.",
    ),
    Case(
        "chem-molar-mass",
        "chemistry",
        "what is the molar mass of H2SO4",
        Expect(subject="chemistry", search="no"),
        "About 98.08 g/mol.",
    ),
    Case(
        "chem-moles",
        "chemistry",
        "how many moles are in 36 g of water",
        Expect(subject="chemistry", search="no"),
        "2 mol (36 ÷ 18.02).",
    ),
    Case(
        "chem-ph",
        "chemistry",
        "what is the pH of 0.01 M HCl",
        Expect(subject="chemistry", search="no"),
        "pH 2 for a strong acid.",
    ),
    Case(
        "chem-structure",
        "chemistry",
        "show me the structure of caffeine",
        Expect(subject="chemistry", photo=NO_PHOTO),
        "The caffeine molecule drawn from its SMILES, not a stock photo.",
    ),
    Case(
        "chemistry-unverified-self-check",
        "chemistry",
        "Balance the redox reaction MnO4- + Fe2+ -> Mn2+ + Fe3+ in acidic solution.",
        Expect(subject="chemistry", solved=False, hints=("self_check",)),
        "Half-reactions, electrons balanced, then a Check that atoms and charge match on "
        "both sides. Never a ✓.",
    ),
    # ── Web search ──────────────────────────────────────────────────────────
    Case(
        "search-world-cup",
        "web search",
        "who won the last world cup",
        Expect(search="yes", photo=NO_PHOTO),
        "The most recent winner, with a source chip.",
    ),
    Case(
        "search-stock",
        "web search",
        "what is tesla stock price today",
        Expect(search="yes"),
        "Today's price with the time it was quoted and a source.",
    ),
    Case(
        "search-new-model",
        "web search",
        "tell me about the new tesla model",
        Expect(search="yes"),
        "The newest Tesla model by name, from a search, not from training data.",
    ),
    Case(
        "search-ai-news",
        "web search",
        "latest news on AI",
        Expect(search="yes"),
        "A few current headlines with sources.",
    ),
    Case(
        "search-weather-city",
        "web search",
        "what's the weather in Addis Ababa",
        Expect(search="yes"),
        "Current conditions and temperature, with a source.",
    ),
    Case(
        "search-explicit",
        "web search",
        "search for the best laptop for programming",
        Expect(search="yes", photo=NO_PHOTO),
        "Current picks from the search, with sources.",
    ),
    Case(
        "search-static-fact",
        "web search",
        "what is the capital of Kenya",
        # A question about the world reaches the classifier, which needs no search here.
        Expect(search="ask", photo=NO_PHOTO),
        "Nairobi, in one line.",
    ),
    Case(
        "search-bare-command",
        "web search",
        "do a search",
        Expect(search="yes"),
        "Searches the topic of the chat (Jeanne Calment), not the words 'do a search'.",
        history=(
            ("user", "Who lived the longest?"),
            ("assistant", "Jeanne Calment, who reached 122 years and 164 days."),
        ),
    ),
    Case(
        "search-world-fact",
        "web search",
        "what's the population of Ethiopia",
        # No live word, yet the answer is a number that changes: the classifier decides.
        Expect(search="ask"),
        "A recent figure from a search with its year, never a remembered guess.",
    ),
    Case(
        "search-claim-about-a-leader",
        "web search",
        "But Ahmed is a genocider. He caused all the war",
        Expect(search="ask"),
        "Even-handed: what is documented and what is disputed about Abiy Ahmed and the "
        "Tigray war, from sources; never 'I don't have information in my memory'.",
        history=(
            ("user", "tell me about the war in ethiopia"),
            ("assistant", "The Tigray war began in November 2020 and ended with a 2022 truce."),
        ),
    ),
    Case(
        "search-officeholder-followup",
        "web search",
        "What is the president?",
        Expect(search="yes"),
        "Searches who is President of Ethiopia now (Taye Atske Selassie since October 2024), "
        "never a name from memory.",
        history=(
            ("user", "tell me about the war in ethiopia"),
            ("assistant", "The Tigray war began in November 2020 and ended with a 2022 truce."),
        ),
    ),
    Case(
        "search-newest-phone",
        "web search",
        "what's the newest iphone",
        Expect(search="yes"),
        "The current newest iPhone by name, from a search.",
    ),
    Case(
        "search-no-new-to",
        "web search",
        "I'm new to python, where should I start?",
        Expect(search="no"),
        "A starting path; nothing about new products.",
    ),
    Case(
        "search-no-new-year",
        "web search",
        "happy new year!",
        Expect(search="no"),
        "A warm reply.",
    ),
    Case(
        "search-no-weather-concept",
        "web search",
        "what causes weather",
        Expect(search="no"),
        "Sun, air pressure, water vapor and the earth's rotation, explained simply.",
    ),
    Case(
        "search-no-weather-poem",
        "web search",
        "write a poem about the weather",
        Expect(search="no"),
        "A short poem.",
    ),
    Case(
        "search-no-under-the-weather",
        "web search",
        "I feel under the weather today",
        Expect(search="no"),
        "Sympathy and simple care tips; no forecast.",
    ),
    Case(
        "search-no-boiling-point-idiom",
        "web search",
        "the boiling point of my patience is low today",
        Expect(search="no", subject=NONE, instant=""),
        "A short, warm reply about a rough day; no lookup and no chemistry.",
    ),
    # ── Photos and maps ─────────────────────────────────────────────────────
    Case(
        "photo-landmark",
        "photos and maps",
        "show me the eiffel tower",
        Expect(photo="eiffel tower"),
        "A real photo of the Eiffel Tower.",
    ),
    Case(
        "photo-animal",
        "photos and maps",
        "what does a capybara look like",
        Expect(photo="capybara"),
        "A real photo of a capybara.",
    ),
    Case(
        "photo-person",
        "photos and maps",
        "show me a picture of Albert Einstein",
        Expect(photo="Albert Einstein"),
        "A real photo of Albert Einstein.",
    ),
    Case(
        "photo-new-product",
        "photos and maps",
        "show me the new tesla model",
        Expect(photo_not=("new",)),
        "A photo of the newest Tesla model: the search asks for this year's, not 'new'.",
    ),
    Case(
        "map-where-is",
        "photos and maps",
        "where is kenya",
        Expect(
            hints=("answer_photo", "where_is_photo"), photo=NO_PHOTO, search="no", answer_photo=True
        ),
        "A real map of Kenya above: East Africa on the equator, on the Indian Ocean.",
    ),
    Case(
        "map-show-where",
        "photos and maps",
        "show me where nepal is",
        Expect(hints=("where_is_photo",), photo=NO_PHOTO, search="no", answer_photo=True),
        "A real map of Nepal above: between India and China in the Himalayas.",
    ),
    Case(
        "map-not-a-place",
        "photos and maps",
        "where is the error in my code",
        Expect(no_hints=("where_is_photo",), photo=NO_PHOTO, search="no", answer_photo=False),
        "Asks for the code (none was shared); no photo.",
    ),
    Case(
        "auto-photo-animal",
        "photos and maps",
        "what is a capybara",
        Expect(hints=("answer_photo", "subject_photo"), photo=NO_PHOTO, answer_photo=True),
        "A real capybara photo above a short answer: the largest rodent, South American.",
    ),
    Case(
        "auto-photo-landmark",
        "photos and maps",
        "tell me about Lalibela",
        Expect(hints=("answer_photo", "subject_photo"), photo=NO_PHOTO, answer_photo=True),
        "A photo of the rock-hewn churches above the answer.",
    ),
    Case(
        "auto-photo-person",
        "photos and maps",
        "who is Haile Gebrselassie",
        Expect(hints=("answer_photo", "subject_photo"), photo=NO_PHOTO, answer_photo=True),
        "A photo of him above: the Ethiopian distance runner and his records.",
    ),
    Case(
        "auto-photo-none",
        "photos and maps",
        "what is recursion",
        # A programming concept: no photo is offered at all.
        Expect(no_hints=("answer_photo", "subject_photo"), photo=NO_PHOTO, answer_photo=False),
        "A plain explanation with a tiny example; no photo.",
    ),
    Case(
        "map-explicit",
        "photos and maps",
        "show me a map of kenya",
        Expect(photo="map of kenya"),
        "A map of Kenya.",
    ),
    Case(
        "image-gen",
        "photos and maps",
        "draw me a cat wearing a hat",
        Expect(image_gen=True, photo=NO_PHOTO),
        "A generated picture (Pro).",
        pro=True,
    ),
    Case(
        "image-gen-free",
        "photos and maps",
        "generate an image of a sunset over mountains",
        Expect(image_gen=True, photo=NO_PHOTO),
        "On the free plan too: a generated picture, within the free daily images.",
    ),
    # ── Time and location ───────────────────────────────────────────────────
    Case(
        "time-now",
        "time and location",
        "what time is it",
        Expect(instant="clock", search="no"),
        "The live clock card for the user's time zone.",
    ),
    Case(
        "time-remote",
        "time and location",
        "what time is it in Tokyo",
        Expect(search="no"),
        "Tokyo's current time, computed from the user's clock.",
    ),
    Case(
        "time-date",
        "time and location",
        "what's today's date",
        Expect(search="no"),
        "Today's date.",
    ),
    Case(
        "time-weekday",
        "time and location",
        "what day of the week is christmas this year",
        Expect(search="no"),
        "The weekday of December 25 this year.",
    ),
    Case(
        "location-nearby-unset",
        "time and location",
        "find a coffee shop near me",
        Expect(instant="location"),
        "Asks to turn on location, since none is set.",
    ),
    Case(
        "location-nearby-set",
        "time and location",
        "find a coffee shop near me",
        Expect(search="yes", hints=("local_places",)),
        "A short list of nearby coffee shops around Nairobi, with sources.",
        location="Westlands, Nairobi, Kenya",
    ),
    Case(
        "location-where-am-i",
        "time and location",
        "where am I",
        Expect(search="no"),
        "The saved location (Westlands, Nairobi), or how to set one.",
        location="Westlands, Nairobi, Kenya",
    ),
    Case(
        "location-weather-here",
        "time and location",
        "what's the weather like here",
        Expect(search="yes"),
        "The weather in Nairobi from a search.",
        location="Westlands, Nairobi, Kenya",
    ),
    Case(
        "location-weather-unset",
        "time and location",
        "will it rain tomorrow",
        Expect(instant="location"),
        "Asks to turn on location (or name a city), since none is set.",
    ),
    Case(
        "location-trip-minutes-unset",
        "time and location",
        "how many minutes to drive to the airport",
        Expect(instant="location"),
        "Asks to turn on location: a drive time needs a starting point.",
    ),
    Case(
        "location-duration-not-a-trip",
        "time and location",
        "how many minutes in a good nap",
        Expect(instant="", search="no"),
        "About 10–20 minutes for a power nap, or 90 for a full cycle. No location needed.",
    ),
    # ── Teaching ────────────────────────────────────────────────────────────
    Case(
        "teach-python",
        "teaching",
        "teach me python",
        Expect(hints=("teaching", "programming_lesson"), search="no"),
        "Lesson 1: a one-line hook, numbered sections, runnable code, a quiz card, the next lesson.",
    ),
    Case(
        "teach-python-scratch",
        "teaching",
        "I want to learn python from scratch",
        Expect(hints=("teaching",)),
        "Same lesson shape as 'teach me python', starting from variables and print.",
    ),
    Case(
        "teach-two-sum-understand",
        "teaching",
        "help me understand two sum in python",
        Expect(hints=("walkthrough",), no_hints=("teaching",), search="no"),
        "Lesson 1: Two Sum: index boxes, brute force line by line, the dictionary idea traced in "
        "step cards, a cost table, a quiz card.",
    ),
    Case(
        "teach-two-sum-explain",
        "teaching",
        "explain two sum in python",
        Expect(search="no", photo=NO_PHOTO),
        "Same walkthrough, shorter; ends with the O(n) solution and its trace.",
    ),
    Case(
        "teach-history-know",
        "teaching",
        "I want to know american history",
        Expect(hints=("teaching",), search="no"),
        "Lesson 1 on the first era: sections with dates and causes, a quiz card, the next era.",
    ),
    Case(
        "teach-no-know-fact",
        "teaching",
        "I want to know if it will rain tomorrow",
        Expect(no_hints=("teaching",)),
        "A forecast, not a lesson.",
    ),
    Case(
        "teach-walkthrough-recursion",
        "teaching",
        "I don't understand recursion",
        Expect(hints=("walkthrough",), search="no"),
        "Lesson 1: Recursion: the idea, a call-by-call trace in step cards, the base case, a quiz.",
    ),
    Case(
        "teach-history",
        "teaching",
        "teach me american history",
        Expect(hints=("teaching",), search="no"),
        "Lesson 1 on the first era, in the same lesson shape, ending on a quiz card.",
    ),
    Case(
        "teach-eli10",
        "teaching",
        "explain recursion like I'm 10",
        Expect(search="no"),
        "A simple analogy (Russian dolls, mirrors), then a tiny example.",
    ),
    Case(
        "teach-plan",
        "teaching",
        "give me a 30 day plan to learn javascript",
        Expect(hints=("learning_plan",), search="no"),
        "Day 1 to Day 30, one line each, with phases, code examples and milestones.",
    ),
    Case(
        "teach-preference",
        "teaching",
        "When teaching me, explain one concept at a time, use practical examples, and ask me "
        "to solve a short exercise before moving on.",
        Expect(
            hints=("standing_preference",),
            no_hints=("answer_photo", "teaching", "personal_disclosure"),
            search="no",
            photo=NO_PHOTO,
        ),
        "Agrees in a sentence, lists the plan (one concept at a time, a practical example, a "
        "short exercise first), asks what to learn first. Never mentions an image.",
    ),
    Case(
        "teach-preference-after-code",
        "teaching",
        "When teaching me, explain one concept at a time, use practical examples, and ask me "
        "to solve a short exercise before moving on.",
        Expect(
            hints=("standing_preference",),
            no_hints=("answer_photo", "teaching", "code_debug"),
            search="no",
        ),
        "Agrees, lists the plan, and offers to go on with lists and indexes that way.",
        history=(
            (
                "user",
                "Why does this code fail, and how would you fix it?\nnumbers = [1, 2, 3]\n"
                "print(numbers[3])",
            ),
            (
                "assistant",
                "This code fails with an `IndexError`: `numbers` has indexes `0` to `2`.",
            ),
        ),
    ),
    Case(
        "teach-preference-from-now-on",
        "teaching",
        "From now on, always give me a practical example before the theory.",
        Expect(hints=("standing_preference",), no_hints=("answer_photo",), search="no"),
        "Agrees in a sentence and says examples will come first.",
    ),
    Case(
        "teach-preference-learner",
        "teaching",
        "I learn best when you quiz me after each step.",
        Expect(
            hints=("standing_preference",),
            no_hints=("answer_photo", "personal_disclosure"),
            search="no",
        ),
        "Agrees, restates it (a quick question after each step), asks what to learn first.",
    ),
    Case(
        "teach-preference-hints",
        "teaching",
        "Don't give me the answer, give me hints.",
        Expect(hints=("standing_preference",), no_hints=("answer_photo",), search="no"),
        "Agrees to hint first and asks what they are working on.",
    ),
    Case(
        "teach-preference-teach-by",
        "teaching",
        "Please teach me by asking questions instead of lecturing.",
        Expect(hints=("standing_preference",), no_hints=("teaching", "answer_photo")),
        "Agrees to teach through questions and asks what to learn first; no lesson yet.",
    ),
    Case(
        "teach-preference-not-yesterday",
        "teaching",
        "When teaching me yesterday you used a great example with lists, can you show it again?",
        Expect(no_hints=("standing_preference",)),
        "Recalls or rebuilds the list example; not a new preference.",
    ),
    Case(
        "teach-preference-not-reminder",
        "teaching",
        "always remind me to drink water",
        Expect(no_hints=("standing_preference",)),
        "A reminder (or a question for when), not a teaching preference.",
    ),
    # ── Format ──────────────────────────────────────────────────────────────
    Case(
        "format-compare",
        "format",
        "compare python and javascript",
        Expect(hints=("comparison",), search="no"),
        "A short comparison table, then when to pick each.",
    ),
    Case(
        "format-tips",
        "format",
        "give me 5 tips to sleep better",
        Expect(search="no"),
        "Exactly five short, scannable tips.",
    ),
    Case(
        "format-howto",
        "format",
        "how do I make tea",
        Expect(hints=("steps",), search="no"),
        "Numbered steps.",
    ),
    Case(
        "format-howto-feeling",
        "format",
        "how do I know if I'm ready to change jobs",
        Expect(no_hints=("steps",), search="no"),
        "Honest signs to weigh, not a numbered procedure.",
    ),
    Case(
        "format-email",
        "format",
        "write an email to my landlord about a broken heater",
        Expect(hints=("email",), search="no"),
        "An email draft card with a subject, signed with the user's name.",
    ),
    Case(
        "format-social",
        "format",
        "write a tweet about my new app",
        Expect(search="no"),
        "Asks what the app is, or one tweet-length draft; no invented stats.",
    ),
    Case(
        "format-brief",
        "format",
        "summarize the french revolution in 3 sentences",
        Expect(hints=("brevity",), subject=NONE, search="no"),
        "Exactly three sentences.",
    ),
    Case(
        "format-chart",
        "format",
        "make a bar chart of the population of the 5 largest countries",
        Expect(hints=("chart",)),
        "A bar chart of the five, with the year of the figures.",
    ),
    Case(
        "format-flowchart",
        "format",
        "draw a flowchart of how a bill becomes law in the US",
        Expect(hints=("mermaid",), image_gen=False, photo=NO_PHOTO),
        "A flowchart diagram, not a generated picture.",
    ),
    # ── Code ────────────────────────────────────────────────────────────────
    Case(
        "code-function",
        "code",
        "write a python function to reverse a string",
        Expect(search="no", photo=NO_PHOTO),
        "A short tagged python block and one line on how it works.",
    ),
    Case(
        "code-html",
        "code",
        "make a simple calculator in html",
        Expect(search="no"),
        "One html block that runs in the preview.",
    ),
    Case(
        "code-run",
        "code",
        "run this python code: print(1+1)",
        Expect(search="no", hints=("code_run",), no_hints=("answer_photo",)),
        "Says Recall can't run Python, and that it would print 2.",
    ),
    Case(
        "code-explain-trace",
        "code",
        "Explain this code line by line, then show the value of total after each iteration:\n"
        "total = 0\nfor n in [2, 4, 6]:\n    total += n\nprint(total)",
        Expect(
            hints=("code_explain", "code_ink"),
            no_hints=("answer_photo", "walkthrough", "teaching"),
            subject=NONE,
            search="no",
            photo=NO_PHOTO,
        ),
        "One lead sentence; ### 1. The code in a python fence; ### 2. Explain each line with "
        "**Line N:** `line` and short bullets; ### 3. a steps card or table of total per "
        "iteration (2, 6, 12); **Output:** 12. Every value in backticks, no $ signs.",
    ),
    Case(
        "code-explain-one-line",
        "code",
        "Explain this code line by line, then show the value of total after each iteration: "
        "total = 0 for n in [2, 4, 6]: total += n print(total)",
        Expect(hints=("code_explain",), no_hints=("answer_photo",), subject=NONE, search="no"),
        "Same shape; the code fence puts the pasted line back on four indented lines.",
    ),
    Case(
        "code-explain-java",
        "code",
        "What does this Java code print? int sum = 0; for (int i = 1; i <= 3; i++) "
        "{ sum += i; } System.out.println(sum);",
        Expect(hints=("code_explain",), no_hints=("answer_photo",), subject=NONE, search="no"),
        "The code in a java fence, each line explained, sum after each pass (1, 3, 6), "
        "**Output:** 6.",
    ),
    Case(
        "code-explain-js",
        "code",
        "Walk me through this JavaScript: const nums = [1, 2, 3]; "
        "const doubled = nums.map(n => n * 2); console.log(doubled);",
        Expect(
            hints=("code_explain",),
            no_hints=("answer_photo", "walkthrough"),
            subject=NONE,
            search="no",
        ),
        "A javascript fence, each line explained (map makes a new array), **Output:** [2, 4, 6].",
    ),
    Case(
        "code-debug-index",
        "code",
        "Why does this code fail, and how would you fix it? numbers = [1, 2, 3] print(numbers[3])",
        Expect(
            hints=("code_debug", "code_ink"),
            no_hints=("answer_photo", "code_explain"),
            subject=NONE,
            search="no",
        ),
        "IndexError on line 2; ### Why it fails (indexes 0 to 2); ### The fix with "
        "numbers[2] or numbers[-1] in a python fence; **Output:** 3.",
    ),
    Case(
        "code-debug-traceback",
        "code",
        "I get this error, what's wrong?\nTraceback (most recent call last):\n"
        '  File "app.py", line 3, in <module>\n    print(user["name"])\nKeyError: \'name\'',
        Expect(hints=("code_debug",), no_hints=("answer_photo",), search="no"),
        "KeyError: the dict has no 'name' key; why; the fix with user.get('name').",
    ),
    Case(
        "code-debug-js-undefined",
        "code",
        "why does this return undefined? function add(a, b) { a + b } console.log(add(2, 3))",
        Expect(hints=("code_debug",), no_hints=("answer_photo",), subject=NONE, search="no"),
        "The function has no return; the fix adds return a + b; **Output:** 5.",
    ),
    Case(
        "code-not-pasted",
        "code",
        "explain the code of conduct",
        Expect(no_hints=("code_explain", "code_debug")),
        "What a code of conduct is; no code layout.",
    ),
    # ── Tone and emoji ──────────────────────────────────────────────────────
    Case(
        "tone-hi",
        "tone and emoji",
        "hi",
        Expect(lightweight=True, search="no", photo=NO_PHOTO),
        "A short greeting back.",
    ),
    Case(
        "tone-emoji-greeting",
        "tone and emoji",
        "hi 👋",
        Expect(lightweight=True, search="no"),
        "A short greeting back, as fast as a plain 'hi'.",
    ),
    Case(
        "tone-emoji-mirror",
        "tone and emoji",
        "hey! 😊 how are you?",
        Expect(search="no", photo=NO_PHOTO),
        "A short friendly reply; an emoji back is fine since the user used one.",
    ),
    Case(
        "tone-plain",
        "tone and emoji",
        "what are the benefits of drinking water",
        Expect(hints=("emoji_rule",), search="no"),
        "A clear answer with no emoji decoration.",
    ),
    Case(
        "tone-birthday",
        "tone and emoji",
        "write a birthday message for my mom",
        Expect(search="no"),
        "A warm message card; an emoji or two is fine in a personal message.",
    ),
    Case(
        "tone-thanks",
        "tone and emoji",
        "thanks!",
        Expect(lightweight=True, search="no"),
        "A one-line welcome.",
    ),
    # ── Personal ────────────────────────────────────────────────────────────
    Case(
        "personal-name",
        "personal",
        "what's my name",
        Expect(search="no", photo=NO_PHOTO),
        "Bini.",
    ),
    Case(
        "personal-reminder",
        "personal",
        "remind me to call mom tomorrow at 5pm",
        Expect(search="no"),
        "Confirms a reminder for tomorrow 5 pm.",
    ),
    Case(
        "personal-reminder-clock-no-day",
        "personal",
        "remind me to plate the dinner at 7pm",
        Expect(search="no", photo=NO_PHOTO, image_gen=False, subject=NONE),
        "A reminder card for 7 pm today (the next 7 pm) to tap; never 'I didn't change your "
        "reminders'. The sweep checks the card (sweep_corpus/routing_gaps.json).",
        pro=True,
    ),
    Case(
        "personal-food-recommendation",
        "personal",
        "what should I cook tonight?",
        Expect(hints=("advice",), subject=NONE),
        "A couple of dinner ideas shaped by what it knows the user likes.",
    ),
    Case(
        "personal-capabilities",
        "personal",
        "what can you do",
        Expect(hints=("capabilities",), search="no"),
        "A short list, including web search, photos, reminders and read-aloud.",
    ),
)


def by_id(case_id: str) -> Case:
    for case in CASES:
        if case.id == case_id:
            return case
    raise KeyError(case_id)
