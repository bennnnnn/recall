from dataclasses import replace

import pytest
from pydantic import ValidationError

from app.content.learning_catalog import LessonDeck, LessonPath, LessonWord
from app.content.vocab_banks_en import english_decks, english_path_decks
from app.content.vocab_banks_es import spanish_decks
from app.content.vocab_catalog import all_catalog_decks, path_decks_for_language, word_id


@pytest.mark.parametrize("language,legacy", [("en", english_path_decks), ("es", spanish_decks)])
def test_enrichment_preserves_existing_ids_order_and_pronunciation(language, legacy):
    old_path = legacy()
    active_path = path_decks_for_language(language)
    assert len(active_path) > len(old_path)
    for old, active in zip(old_path, active_path, strict=False):
        assert (old.id, old.title, old.domain, old.sort_order) == (
            active.id,
            active.title,
            active.domain,
            active.sort_order,
        )
        assert [word_id(old, word) for word in old.words] == [
            word_id(active, word) for word in active.words
        ]
        assert [word.ipa for word in old.words] == [word.ipa for word in active.words]


def test_all_legacy_ids_remain_resolvable_with_active_content_winning():
    entries = {word_id(deck, word): word for deck in all_catalog_decks() for word in deck.words}
    for old_deck in [*spanish_decks(), *english_decks()]:
        assert all(word_id(old_deck, word) in entries for word in old_deck.words)
    for language in ("en", "es"):
        for active in path_decks_for_language(language):
            for word in active.words:
                assert entries[word_id(active, word)] == word


@pytest.mark.parametrize("language,count", [("en", 387), ("es", 519)])
def test_every_active_sense_has_definition_distinct_examples_and_classification(language, count):
    words = [word for deck in path_decks_for_language(language) for word in deck.words]
    assert len(words) == count
    for word in words:
        assert word.definition.strip(), word.content
        assert word.definition.casefold() != word.content.casefold(), word.content
        examples = (word.example_sentence or "").splitlines()
        assert len(examples) >= 2, word.content
        assert len({example.casefold().strip() for example in examples}) == len(examples)
        assert word.part_of_speech, word.content
        if word.part_of_speech == "noun":
            assert word.noun_kind, word.content
        if word.part_of_speech == "verb":
            assert word.verb_kind, word.content
    kinds = {word.vocabulary_kind for word in words}
    assert {"word", "expression", "idiom", "proverb"} <= kinds
    if language == "en":
        assert "phrasal_verb" in kinds


def test_spanish_hogar_keeps_different_senses_in_their_original_chapters():
    senses = [
        (deck, word)
        for deck in path_decks_for_language("es")
        for word in deck.words
        if word.content == "hogar"
    ]
    assert len(senses) == 2
    assert len({word_id(deck, word) for deck, word in senses}) == 2
    assert len({word.definition for _, word in senses}) == 2


def _sample_word():
    word = path_decks_for_language("en")[0].words[0]
    return {
        "content": word.content,
        "definition": word.definition,
        "example_sentences": word.example_sentence.splitlines(),
        "part_of_speech": word.part_of_speech,
        "vocabulary_kind": word.vocabulary_kind,
    }


@pytest.mark.parametrize("examples", [[], ["Hello."], ["Hello.", "  HELLO.  "]])
def test_catalog_rejects_missing_or_repeated_examples(examples):
    with pytest.raises(ValidationError):
        LessonWord.model_validate({**_sample_word(), "example_sentences": examples})


def test_catalog_rejects_duplicate_word_identity_and_mixed_languages():
    word = _sample_word()
    deck = {
        "language": "en",
        "slug": "greetings",
        "title": "Greetings",
        "domain": "Greetings",
        "kind": "chapter",
        "sort_order": 0,
        "words": [word],
    }
    with pytest.raises(ValidationError):
        LessonDeck.model_validate({**deck, "words": [word, {**word, "content": "HELLO"}]})
    with pytest.raises(ValidationError):
        LessonPath.model_validate({"schema_version": 1, "language": "es", "decks": [deck]})


def test_returned_path_list_cannot_change_the_cached_catalog():
    decks = path_decks_for_language("en")
    first = decks[0]
    decks[0] = replace(first, words=())
    decks.clear()
    assert path_decks_for_language("en")[0] == first
