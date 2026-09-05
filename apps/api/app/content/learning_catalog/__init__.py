"""Validated, versioned lesson content. Legacy banks retain historical IDs."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.content.vocab_catalog import CatalogDeck, CatalogWord

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Language = Literal["en", "es"]


class _Content(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LessonWord(_Content):
    content: Text
    definition: Text
    example_sentences: list[Text] = Field(min_length=2)
    ipa: Text | None = None
    part_of_speech: Text
    simple_gloss: Text | None = None
    vocabulary_kind: Literal["word", "expression", "phrasal_verb", "idiom", "proverb"]
    verb_kind: Literal["action", "state", "auxiliary", "modal"] | None = None
    noun_kind: Literal["common", "proper", "abstract", "collective"] | None = None

    @model_validator(mode="after")
    def distinct_examples(self) -> Self:
        normalized = {" ".join(example.casefold().split()) for example in self.example_sentences}
        if len(normalized) != len(self.example_sentences):
            raise ValueError("Lesson examples must be distinct")
        if any("\n" in example for example in self.example_sentences):
            raise ValueError("Each example must be a single paragraph")
        if self.verb_kind and self.noun_kind:
            raise ValueError("Classify the taught sense as a verb or noun, never both")
        return self


class LessonDeck(_Content):
    language: Language
    slug: Text
    title: Text
    domain: Text
    kind: Literal["chapter"]
    sort_order: int = Field(ge=0)
    words: list[LessonWord] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_words(self) -> Self:
        if len({word.content.casefold() for word in self.words}) != len(self.words):
            raise ValueError("Words must have unique identities within a chapter")
        return self


class LessonPath(_Content):
    schema_version: Literal[1]
    language: Language
    decks: list[LessonDeck] = Field(min_length=1)

    @model_validator(mode="after")
    def consistent_path(self) -> Self:
        if any(deck.language != self.language for deck in self.decks):
            raise ValueError("Every chapter must use the path language")
        for field in ("slug", "title", "sort_order"):
            if len({getattr(deck, field) for deck in self.decks}) != len(self.decks):
                raise ValueError(f"Chapters must have unique {field}")
        if self.decks != sorted(self.decks, key=lambda deck: deck.sort_order):
            raise ValueError("Chapters must be in learning order")
        return self


@lru_cache(maxsize=2)
def load_path(language: Language) -> tuple[CatalogDeck, ...]:
    path = Path(__file__).with_name(f"{language}.json")
    data = LessonPath.model_validate_json(path.read_text(encoding="utf-8"))
    if data.language != language:
        raise ValueError("Catalog file has the wrong language")
    return tuple(
        CatalogDeck(
            language=deck.language,
            slug=deck.slug,
            title=deck.title,
            domain=deck.domain,
            kind=deck.kind,
            sort_order=deck.sort_order,
            words=tuple(
                CatalogWord(
                    **word.model_dump(exclude={"example_sentences"}),
                    example_sentence="\n".join(word.example_sentences),
                )
                for word in deck.words
            ),
        )
        for deck in data.decks
    )
