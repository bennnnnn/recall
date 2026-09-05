from dataclasses import replace
from hashlib import sha256

import pytest
from pydantic import ValidationError

from app.content.learning_catalog import LessonDeck, LessonPath, LessonWord
from app.content.vocab_catalog import all_catalog_decks, path_decks_for_language, word_id


@pytest.mark.parametrize(
    "language,slugs,identity_digest",
    [
        (
            "en",
            [
                "conversation-expressions",
                "everyday-phrasal-verbs",
                "everyday-idioms",
                "common-proverbs",
            ],
            "d78660918d60fbc0f7dceb6881fc1b0bbf463fa34ff10aad9eab8c398bccd1f1",
        ),
        (
            "es",
            ["everyday-idioms", "everyday-proverbs"],
            "09f7476cdc3feebe6780b882bc5caa2d79516a6a61c07a6004ef9abfac0aaf0b",
        ),
    ],
)
def test_only_requested_new_groups_have_the_approved_word_ids(language, slugs, identity_digest):
    decks = path_decks_for_language(language)
    assert [deck.slug for deck in decks] == slugs
    assert all(len(deck.words) == 10 for deck in decks)
    identities = sorted(str(word_id(deck, word)) for deck in decks for word in deck.words)
    assert sha256("\n".join(identities).encode()).hexdigest() == identity_digest


def test_product_catalog_contains_only_the_sixty_new_active_entries():
    decks = all_catalog_decks()
    assert len(decks) == 6
    entries = {word_id(deck, word): word for deck in decks for word in deck.words}
    assert len(entries) == 60
    assert all(word.vocabulary_kind != "word" for word in entries.values())
    assert not {
        "hello",
        "hi",
        "hola",
        "madre",
        "father",
        "one",
        "uno",
        "run",
        "turn on",
        "turn off",
        "look for",
    } & {word.content.casefold() for word in entries.values()}


@pytest.mark.parametrize("language,count", [("en", 40), ("es", 20)])
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
    assert kinds == (
        {"expression", "phrasal_verb", "idiom", "proverb"}
        if language == "en"
        else {"idiom", "proverb"}
    )


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
        LessonDeck.model_validate(
            {**deck, "words": [word, {**word, "content": word["content"].upper()}]}
        )
    with pytest.raises(ValidationError):
        LessonPath.model_validate({"schema_version": 1, "language": "es", "decks": [deck]})


def test_returned_path_list_cannot_change_the_cached_catalog():
    decks = path_decks_for_language("en")
    first = decks[0]
    decks[0] = replace(first, words=())
    decks.clear()
    assert path_decks_for_language("en")[0] == first
