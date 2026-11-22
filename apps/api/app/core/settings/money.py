"""Money: loans, card payoff and savings, with today's average rates (docs/money.md)."""

from pydantic import BaseModel


class MoneySettings(BaseModel):
    # Loan, card and savings questions get server-worked numbers and a calculator card.
    money_enabled: bool = True
    # Today's average rate is looked up on the web once per product, term and country,
    # and kept this long: averages move weekly at most.
    money_rate_cache_seconds: int = 43_200
    # A rate below the average divided by this, or above it times this, "is not realistic".
    money_unrealistic_ratio: float = 2.0
    # A turn the read calls money (``chat.turn_decision``: subject money) that no word rule
    # read has a model write the chat's request down, each value held to the chat's words
    # (``money.model_read``, ``money.read_check``); the server works the numbers.
    money_read_enabled: bool = True
    # The prompt waits this long for that read at most.
    money_read_timeout_seconds: float = 3.0
