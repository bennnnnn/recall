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
from app.content.vocab_banks_en.hello import hello_decks
from app.content.vocab_banks_en.home import home_decks
from app.content.vocab_banks_en.hotel import hotel_decks
from app.content.vocab_banks_en.household import household_decks
from app.content.vocab_banks_en.movement import movement_decks
from app.content.vocab_banks_en.numbers import numbers_decks
from app.content.vocab_banks_en.reactions import reactions_decks
from app.content.vocab_banks_en.sat import sat_decks
from app.content.vocab_banks_en.thinking import thinking_decks
from app.content.vocab_banks_en.travel import travel_decks
from app.content.vocab_catalog import CatalogDeck, merge_decks_by_domain


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


def english_path_source_decks() -> list[CatalogDeck]:
    """Per-theme banks before collapsing to one map node per domain."""
    return [
        *hello_decks(),
        *feelings_decks(),
        *everyday_actions_decks(),
        *communication_decks(),
        *thinking_decks(),
        *describing_decks(),
        *conversation_decks(),
        *american_decks(),
        *body_sounds_decks(),
        *eating_decks(),
        *face_decks(),
        *movement_decks(),
        *hands_decks(),
        *reactions_decks(),
        *household_decks(),
    ]


def english_path_decks() -> list[CatalogDeck]:
    """Conversation-grouped English lesson map — one group per theme."""
    return merge_decks_by_domain(english_path_source_decks())


def english_decks() -> list[CatalogDeck]:
    return [*english_legacy_decks(), *english_path_source_decks()]
