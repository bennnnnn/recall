from collections import Counter

import pytest

from app.content.vocab_catalog import (
    catalog_domain_by_title,
    catalog_domains,
    catalog_path_titles,
    catalog_word_count,
    decks_for_language,
    path_decks_for_language,
    word_id,
)
from app.services.learning.catalog_sync import _sync_decks


def test_spanish_catalog_contains_only_new_idioms_and_proverbs():
    assert catalog_path_titles("es") == ["Everyday Idioms", "Everyday Proverbs"]
    assert catalog_domains("es") == ["Idioms and Proverbs"]
    assert catalog_word_count("es") == 20


def test_english_catalog_contains_only_new_expression_groups():
    expected = [
        "Useful conversation expressions",
        "Everyday phrasal verbs",
        "Everyday idioms",
        "Common proverbs",
    ]
    assert catalog_path_titles("en") == catalog_domains("en") == expected
    assert catalog_word_count("en") == 40


@pytest.mark.parametrize("language,count", [("en", 40), ("es", 20)])
def test_include_sat_cannot_restore_retired_groups(language, count):
    active = path_decks_for_language(language)
    assert decks_for_language(language, include_sat=True) == active
    assert catalog_domains(language, include_sat=True) == catalog_domains(language)
    assert catalog_word_count(language, include_sat=True) == count
    assert all(deck.kind == "chapter" for deck in active)
    assert not {"Greetings", "Family", "Home", "SAT", "SAT words", "Hotel services"} & {
        deck.title for deck in active
    }
    assert "hello and goodbye" not in catalog_domain_by_title(language, include_sat=True)
    assert "please and thanks" not in catalog_domain_by_title(language, include_sat=True)


def test_catalog_sync_contains_exactly_active_ids_and_no_historical_source_rows():
    active = [*path_decks_for_language("en"), *path_decks_for_language("es")]
    synchronized = _sync_decks()
    assert synchronized == active
    assert len(synchronized) == 6
    assert {word_id(deck, word) for deck in synchronized for word in deck.words} == {
        word_id(deck, word) for deck in active for word in deck.words
    }


def test_english_expression_cards_have_study_fields():
    for deck in path_decks_for_language("en"):
        assert len(deck.words) == 10
        assert deck.title == deck.domain
        for word in deck.words:
            assert word.part_of_speech
            assert word.simple_gloss
            assert word.example_sentence


def test_phrasal_group_teaches_nonliteral_actions_instead_of_device_controls():
    deck = next(
        deck for deck in path_decks_for_language("en") if deck.slug == "everyday-phrasal-verbs"
    )
    words = {word.content: word for word in deck.words}
    assert {"bring up", "carry out", "come up with"} <= words.keys()
    assert not {"turn on", "turn off", "look for"} & words.keys()
    assert words["bring up"].simple_gloss == "raise a topic"
    assert words["carry out"].simple_gloss == "perform a planned task"
    assert words["come up with"].simple_gloss == "think of an idea"


def test_catalog_words_and_titles_are_unique():
    for language in ("en", "es"):
        decks = decks_for_language(language)
        titles = [deck.title.casefold() for deck in decks]
        assert len(titles) == len(set(titles))
        words = [word.content.casefold() for deck in decks for word in deck.words]
        assert not [word for word, count in Counter(words).items() if count > 1]


def test_unknown_language_falls_back_to_current_english_only():
    assert catalog_path_titles("xx") == catalog_path_titles("en")
    assert decks_for_language("xx", include_sat=True) == path_decks_for_language("en")
