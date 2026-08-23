from collections import Counter

from app.content.vocab_catalog import (
    catalog_domains,
    catalog_path_titles,
    catalog_word_count,
    decks_for_language,
    level_to_int,
    path_decks_for_language,
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
    # SAT is on the English lesson map; catalog_path_titles still defaults off.
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


def test_lesson_map_is_the_full_tree_not_level_gated():
    assert "Family" in catalog_domains("es")
    assert "Immediate family" in catalog_path_titles("es")
    assert catalog_domains("en") == [
        "Greetings",
        "Family",
        "Food",
        "Home",
        "Hotel",
        "Travel",
        "Daily life",
        "Numbers and time",
    ]
    assert "SAT" in catalog_domains("en", include_sat=True)
    en_path = [deck.domain for deck in path_decks_for_language("en")]
    assert "SAT" in en_path
    es_path = [deck.domain for deck in path_decks_for_language("es")]
    assert "SAT" not in es_path
    assert "Family" in es_path


def test_level_to_int():
    assert level_to_int("level1") == 1
    assert level_to_int("level6") == 6
    assert level_to_int(None) == 1
    assert level_to_int("garbage") == 1
    assert level_to_int("level99") == 6  # clamped
    assert level_to_int("level0") == 1  # clamped


def test_word_count_covers_the_full_bank():
    assert catalog_word_count("en") == sum(len(deck.words) for deck in decks_for_language("en"))
    assert catalog_word_count("en", include_sat=True) > catalog_word_count("en")
