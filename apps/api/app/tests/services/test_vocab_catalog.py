from collections import Counter

from app.content.vocab_catalog import (
    catalog_domains,
    catalog_path_titles,
    catalog_word_count,
    decks_for_language,
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
        "Idioms and Proverbs",
    ]
    family = [deck for deck in decks_for_language("es") if deck.domain == "Family"]
    assert len(family) == 12
    words = {word.content for deck in family for word in deck.words}
    assert "madre" in words
    assert "suegra" in words
    assert catalog_word_count("es") == sum(len(deck.words) for deck in decks_for_language("es"))


def test_english_path_is_conversation_grouped():
    titles = catalog_path_titles("en")
    assert titles[0] == "Greetings"
    assert titles == catalog_domains("en")
    assert "Feelings" in titles
    assert "Please and thanks" not in titles
    assert "Get and give" not in titles
    assert "Hotel services" not in titles
    assert "SAT" not in titles
    assert catalog_domains("en") == [
        "Greetings",
        "Numbers and time",
        "Feelings",
        "Everyday actions",
        "Communication",
        "Thinking",
        "Describing",
        "Conversation words",
        "Face and eyes",
        "Body movement",
        "Hands",
        "Body reactions",
        "Eating and drinking",
        "Household actions",
        "Mouth and body sounds",
        "Casual expressions",
        "Useful conversation expressions",
        "Everyday phrasal verbs",
        "Everyday idioms",
        "Common proverbs",
    ]
    sat_decks = decks_for_language("en", include_sat=True)
    assert any(deck.kind == "sat" for deck in sat_decks)
    sat = next(deck for deck in sat_decks if deck.kind == "sat")
    assert sat.domain == "SAT"
    assert sat.words
    entry = sat.words[0]
    assert word_id(sat, entry) != sat.id
    assert "SAT" not in catalog_domains("en")
    assert "Hotel services" in [deck.title for deck in decks_for_language("en")]


def test_english_path_casual_register_follows_core_topics_and_stays_clean():
    """Keep the original core order; new advanced groups append after it."""
    domains = catalog_domains("en")
    assert domains.index("Casual expressions") == 15
    assert domains[16:] == [
        "Useful conversation expressions",
        "Everyday phrasal verbs",
        "Everyday idioms",
        "Common proverbs",
    ]
    assert "American conversational" not in domains
    all_words = {
        word.content.casefold() for deck in path_decks_for_language("en") for word in deck.words
    }
    assert "sucks" not in all_words
    assert "fart" not in all_words


def test_english_path_practical_topics_have_study_fields_too():
    """Greetings and Numbers and time were promoted from the legacy,
    unenriched tree — confirm they actually got the same ipa /
    part_of_speech / simple_gloss treatment as the rest of the path, not
    just a title on the map."""
    for domain in ("Greetings", "Numbers and time"):
        deck = next(d for d in path_decks_for_language("en") if d.domain == domain)
        assert len(deck.words) >= 16
        for word in deck.words:
            assert word.ipa
            assert word.part_of_speech
            assert word.simple_gloss


def test_english_path_words_have_study_fields():
    for index, deck in enumerate(path_decks_for_language("en")):
        assert deck.words
        for word in deck.words:
            # New multiword groups use the existing device-pronunciation action.
            # Keep verified IPA for every original core word.
            if index < 16:
                assert word.ipa
            assert word.part_of_speech
            assert word.simple_gloss
            assert word.example_sentence


def test_english_path_lemmas_are_unique():
    seen: dict[str, str] = {}
    for deck in path_decks_for_language("en"):
        for word in deck.words:
            key = word.content.casefold()
            assert key not in seen, f"{word.content!r} in {seen[key]} and {deck.slug}"
            seen[key] = deck.slug


def test_english_path_is_one_group_per_theme():
    decks = path_decks_for_language("en")
    assert len(decks) == len({deck.domain for deck in decks})
    for index, deck in enumerate(decks):
        assert deck.title == deck.domain
        if index < 16:
            assert len(deck.words) >= 16
        else:
            assert len(deck.words) == 10


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
    assert "Feelings" in catalog_domains("en")
    assert "SAT" in catalog_domains("en", include_sat=True)
    en_path = [deck.domain for deck in path_decks_for_language("en")]
    assert "SAT" not in en_path
    assert "Hotel" not in en_path
    assert "Feelings" in en_path
    es_path = [deck.domain for deck in path_decks_for_language("es")]
    assert "SAT" not in es_path
    assert "Family" in es_path


def test_word_count_covers_the_path():
    assert catalog_word_count("en") == sum(
        len(deck.words) for deck in path_decks_for_language("en")
    )
    assert catalog_word_count("en", include_sat=True) > catalog_word_count("en")
    assert catalog_word_count("es") == sum(len(deck.words) for deck in decks_for_language("es"))
