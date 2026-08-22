from app.content.vocab_banks_es.daily_life import daily_life_decks
from app.content.vocab_banks_es.family import family_decks
from app.content.vocab_banks_es.food import food_decks
from app.content.vocab_banks_es.greetings import greetings_decks
from app.content.vocab_banks_es.home import home_decks
from app.content.vocab_banks_es.hotel import hotel_decks
from app.content.vocab_banks_es.numbers import numbers_decks
from app.content.vocab_banks_es.travel import travel_decks
from app.content.vocab_catalog import CatalogDeck


def spanish_decks() -> list[CatalogDeck]:
    return [
        *greetings_decks(),
        *family_decks(),
        *food_decks(),
        *home_decks(),
        *hotel_decks(),
        *travel_decks(),
        *daily_life_decks(),
        *numbers_decks(),
    ]
