from collections import Counter

from app.content.vocab_catalog import (
    catalog_domains,
    catalog_path_titles,
    catalog_word_count,
    decks_for_language,
    level_to_int,
    word_id,
)


def test_spanish_catalog_is_a_domain_tree():
    titles = catalog_path_titles("es")
    assert titles[0] == "Hello and goodbye"
    assert "Immediate family" in titles
    assert "SAT" not in titles
    assert catalog_domains("es") == [
        "Greetings",
        "Family",
        "Food",
        "Home",
        "Hotel",
        "Travel",
        "Daily life",
        "Numbers and time",
    ]
    family = [deck for deck in decks_for_language("es") if deck.domain == "Family"]
    assert len(family) == 12
    words = {word.content for deck in family for word in deck.words}
    assert "madre" in words
    assert "suegra" in words
    assert catalog_word_count("es") == sum(len(deck.words) for deck in decks_for_language("es"))


def test_english_catalog_includes_sat_domain():
    # SAT is excluded from the default path; opt in explicitly via decks_for_language.
    titles = catalog_path_titles("en")
    assert "Hotel services" in titles
    assert "SAT" not in titles
    sat_decks = decks_for_language("en", include_sat=True)
    assert any(deck.kind == "sat" for deck in sat_decks)
    sat = next(deck for deck in sat_decks if deck.kind == "sat")
    assert sat.domain == "SAT"
    assert sat.words
    entry = sat.words[0]
    assert word_id(sat, entry) != sat.id
    # Default excludes SAT from domains.
    assert "SAT" not in catalog_domains("en")


def test_catalog_leaf_titles_are_unique_per_language():
    for lang in ("en", "es"):
        titles = [deck.title.casefold() for deck in decks_for_language(lang)]
        dupes = [title for title, count in Counter(titles).items() if count > 1]
        assert dupes == []


def test_catalog_words_are_unique_within_a_deck():
    for deck in [*decks_for_language("en"), *decks_for_language("es")]:
        contents = [word.content.casefold() for word in deck.words]
        dupes = [word for word, count in Counter(contents).items() if count > 1]
        assert dupes == [], deck.slug


def test_unknown_language_falls_back_to_english():
    assert catalog_path_titles("xx") == catalog_path_titles("en")


def test_level_filters_domains():
    # Level 1 (beginner): only Greetings + Numbers
    l1 = catalog_domains("en", level=1)
    assert l1 == ["Greetings", "Numbers and time"]
    l1_titles = catalog_path_titles("en", level=1)
    assert "Hello and goodbye" in l1_titles
    assert "Immediate family" not in l1_titles

    # Level 2: adds Family
    l2 = catalog_domains("en", level=2)
    assert l2 == ["Greetings", "Family", "Numbers and time"]

    # Level 3: adds Food + Home
    l3 = catalog_domains("en", level=3)
    assert "Food" in l3 and "Home" in l3 and "Hotel" not in l3

    # Level 5: everything except SAT
    l5 = catalog_domains("en", level=5)
    assert "Daily life" in l5 and "SAT" not in l5

    # Level 6: SAT unlocks (fluent users get SAT via include_sat)
    l6 = catalog_domains("en", level=6, include_sat=True)
    assert "SAT" in l6
    l6_no_sat = catalog_domains("en", level=6)
    assert "SAT" not in l6_no_sat  # default still excludes SAT

    # Spanish follows the same gating
    assert catalog_domains("es", level=1) == ["Greetings", "Numbers and time"]
    assert "Family" not in catalog_domains("es", level=1)


def test_level_to_int():
    assert level_to_int("level1") == 1
    assert level_to_int("level6") == 6
    assert level_to_int(None) == 1
    assert level_to_int("garbage") == 1
    assert level_to_int("level99") == 6  # clamped
    assert level_to_int("level0") == 1  # clamped


def test_word_count_shrinks_with_level():
    assert catalog_word_count("en", level=1) < catalog_word_count("en", level=3)
    assert catalog_word_count("en", level=3) < catalog_word_count("en", level=6)
