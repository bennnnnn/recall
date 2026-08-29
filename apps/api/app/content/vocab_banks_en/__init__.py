from dataclasses import replace

from app.content.vocab_banks_en.american import american_decks
from app.content.vocab_banks_en.body_sounds import body_sounds_decks
from app.content.vocab_banks_en.communication import communication_decks
from app.content.vocab_banks_en.conversation import conversation_decks
from app.content.vocab_banks_en.daily_life import daily_life_decks
from app.content.vocab_banks_en.describing import describing_decks
from app.content.vocab_banks_en.eating import eating_decks
from app.content.vocab_banks_en.everyday_actions import everyday_actions_decks
from app.content.vocab_banks_en.face import face_decks
from app.content.vocab_banks_en.family import family_decks
from app.content.vocab_banks_en.feelings import feelings_decks
from app.content.vocab_banks_en.food import food_decks
from app.content.vocab_banks_en.greetings import greetings_decks
from app.content.vocab_banks_en.hands import hands_decks
from app.content.vocab_banks_en.home import home_decks
from app.content.vocab_banks_en.hotel import hotel_decks
from app.content.vocab_banks_en.household import household_decks
from app.content.vocab_banks_en.movement import movement_decks
from app.content.vocab_banks_en.numbers import numbers_decks
from app.content.vocab_banks_en.reactions import reactions_decks
from app.content.vocab_banks_en.sat import sat_decks
from app.content.vocab_banks_en.thinking import thinking_decks
from app.content.vocab_banks_en.travel import travel_decks
from app.content.vocab_catalog import CatalogDeck, dedupe_words_across_decks, merge_decks_by_domain


def english_legacy_decks() -> list[CatalogDeck]:
    """Older Hotel/SAT tree — kept so existing UUID5 catalog ids stay valid."""
    return [
        *greetings_decks(),
        *family_decks(),
        *food_decks(),
        *home_decks(),
        *hotel_decks(),
        *travel_decks(),
        *daily_life_decks(),
        *numbers_decks(),
        *sat_decks(),
    ]


def english_path_topic_decks() -> list[CatalogDeck]:
    """Practical, grounding vocabulary a learner needs first — greetings and
    numbers/time. Both source files already use one domain per file, so
    merging collapses each into a single right-sized lesson row.

    Family / Food / Home / Daily life / Travel / Hotel are just as well
    organized (see `english_legacy_decks`) but predate the
    ipa / part_of_speech / simple_gloss study fields the map requires —
    `test_english_path_words_have_study_fields` guards this. They stay off
    the map until they get the same enrichment pass Greetings and Numbers
    just got, rather than shipping thinner cards for those chapters only.
    """
    return merge_decks_by_domain([*greetings_decks(), *numbers_decks()])


def english_path_source_decks() -> list[CatalogDeck]:
    """Conversational-glue and physical/descriptive banks before collapsing
    to one map node per domain. `Casual expressions` (informal words like
    "chill", "legit") is ordered last, after every functional category, so
    learners meet it as a bonus once they can already function in English —
    not as an early gate."""
    return [
        *feelings_decks(),
        *everyday_actions_decks(),
        *communication_decks(),
        *thinking_decks(),
        *describing_decks(),
        *conversation_decks(),
        *face_decks(),
        *movement_decks(),
        *hands_decks(),
        *reactions_decks(),
        *eating_decks(),
        *household_decks(),
        *body_sounds_decks(),
        *american_decks(),
    ]


def english_path_decks() -> list[CatalogDeck]:
    """Conversation-grouped English lesson map: practical topics first
    (Greetings, Numbers and time), then conversational-glue and
    physical/descriptive vocabulary, with casual expressions last.

    Cross-deck dedup keeps a lemma from being taught twice under two
    chapters (e.g. `busy` would otherwise appear in both a greeting reply
    and Describing) — the earlier chapter in this order keeps it.
    """
    combined = [
        *english_path_topic_decks(),
        *merge_decks_by_domain(english_path_source_decks()),
    ]
    deduped = dedupe_words_across_decks(combined)
    return [replace(deck, sort_order=index * 10) for index, deck in enumerate(deduped)]


def english_decks() -> list[CatalogDeck]:
    return [*english_legacy_decks(), *english_path_source_decks()]
