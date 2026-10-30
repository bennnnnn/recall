"""A weather question: the forecast or the conditions somewhere, always live.

"Under the weather", a poem about it, the weather on Mars and a temperature science asks
about ("the lowest temperature at which a substance catches fire") are no forecast.
"""

from __future__ import annotations

import re

# Weather is always live; "under the weather" or a poem about it is no forecast.
_WEATHER = re.compile(
    r"\b(?:(?:what(?:['\u2019]s|\s+is|\s+will\s+be)|how(?:['\u2019]s|\s+is))\s+the\s+"
    r"(?:weather|forecast|temperature)"
    r"|weather\s+(?:in|for|at|near|around|like|today|tomorrow|tonight|now|this\s+(?:week|weekend)"
    r"|forecast|report|update)"
    r"|(?:today|tomorrow|tonight)(?:['\u2019]s)?\s+(?:weather|forecast)"
    r"|(?:weather\s+)?forecast\s+(?:for|in|today|tomorrow|tonight|this)"
    # "The lowest temperature at which a substance catches fire", "temperature in kelvin":
    # a science question, not the temperature at a place (a Class 8 book, 2026-10-30).
    r"|temperature\s+(?:outside|today|tomorrow|tonight|right\s+now|(?:in|at)\s+(?!(?:which|whom"
    r"|room|kelvin|celsius|fahrenheit|degrees?|the\s+same|absolute|this|that|a\s+(?:substance"
    r"|body|metal|liquid|gas))\b))"
    r"|(?:(?:will|is)\s+it|^(?:i\s+(?:want|need)\s+to\s+know|(?:can|could)\s+you\s+(?:tell\s+me|check)"
    r"|do\s+you\s+know|i\s+wonder|tell\s+me|check|find\s+out)\s+(?:if|whether)\s+it(?:\s+will"
    r"|['\u2019]ll|\s+is|['\u2019]s))\s+(?:going\s+to\s+|gonna\s+)?(?:rain|snow|storm)(?:ing)?"
    r"|(?:how|is\s+it)\s+(?:hot|cold|warm|humid)\s+(?:is\s+it\s+)?(?:outside|today|out))\b",
    re.IGNORECASE,
)
WEATHER_NOT_A_FORECAST = re.compile(
    r"\b(?:under\s+the\s+weather|weather\s+(?:the|this|that|a)\s+\w+"
    r"|fair[- ]weather|weather(?:ing)?\s+(?:out|through)"
    r"|(?:poem|story|song|essay|haiku|joke|sentence|paragraph)s?\s+(?:about|on)\s+(?:the\s+)?weather"
    r"|(?:mean(?:s|ing)?|definition|synonyms?|spell|spelling)\b.*\bweather"
    r"|weather\b.*\b(?:mean(?:s|ing)?|definition|synonyms?)"
    r"|weather\s+vs\.?\s+whether|whether\s+(?:or|vs)"
    # A temperature science asks about: a scale, or a thing's own ("of boiling water").
    r"|temperature(?![^.?!]*\b(?:today|tonight|tomorrow|now|this\s+(?:week|weekend))\b)"
    r"\s+(?:in\s+(?:kelvin|celsius|fahrenheit|centigrade)|at\s+which"
    r"|of\s+(?:a\s+|an\s+|the\s+)?(?:boiling|melting|freezing|ice|water|steam|sun|human\s+body"
    r"|body|object|substance|liquid|gas|flame|metal|core|surface\s+of))"
    # Weather on/in/of a planet is science ("in mars" found Marseille); "Mars, PA" searches.
    r"|(?:weather|forecast|temperature|climate)(?:\s+[\w'\u2019]+){0,3}?\s+(?:(?:on|in|of|at)"
    r"\s+(?:the\s+)?(?:planet\s+)?(?:mercury|venus|mars|jupiter|saturn|uranus|neptune|pluto"
    r"|moon|titan|europa|io|other\s+planets?|another\s+planet|exoplanets?)\b(?!\s*,)"
    r"|on\s+(?:the\s+)?sun\b))",
    re.IGNORECASE,
)


def is_weather_request(text: str) -> bool:
    """A real forecast or conditions question, not a figure of speech or a writing task.

    "It's forecast to be 24°C. What is that in Fahrenheit?" converts a stated
    temperature; it asks for no forecast.
    """
    if _WEATHER.search(text) is None or WEATHER_NOT_A_FORECAST.search(text) is not None:
        return False
    return not (_STATED_TEMPERATURE.search(text) and _TEMPERATURE_UNIT.search(text))


_STATED_TEMPERATURE = re.compile(r"\d\s*(?:°|degrees?\b)", re.IGNORECASE)
_TEMPERATURE_UNIT = re.compile(r"\b(?:fahrenheit|celsius|kelvin)\b", re.IGNORECASE)
