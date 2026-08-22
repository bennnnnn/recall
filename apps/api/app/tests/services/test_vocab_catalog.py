from collections import Counter

from app.content.vocab_catalog import (
    catalog_domains,
    catalog_path_titles,
    catalog_word_count,
    decks_for_language,
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
