from app.content.vocab_banks_en.daily_life import daily_life_decks
from app.content.vocab_banks_en.family import family_decks
from app.content.vocab_banks_en.food import food_decks
from app.content.vocab_banks_en.greetings import greetings_decks
from app.content.vocab_banks_en.home import home_decks
from app.content.vocab_banks_en.hotel import hotel_decks
from app.content.vocab_banks_en.numbers import numbers_decks
from app.content.vocab_banks_en.sat import sat_decks
from app.content.vocab_banks_en.travel import travel_decks
from app.content.vocab_catalog import CatalogDeck


def english_decks() -> list[CatalogDeck]:
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
