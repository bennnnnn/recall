"""Search gates the behavior sweep found too eager or too shy."""

import pytest

from app.modules.web_search import names_its_place
from app.modules.web_search.detection import _live_lookup_cue, needs_web_search_heuristic
from app.modules.web_search.patterns import is_correspondence_request


@pytest.mark.parametrize(
    "text",
    [
        "Finish line results from Sunday's Chicago Marathon?",
        "What time is sunset tomorrow in Cape Town?",
        "How much is an iPhone 17 in Ethiopia?",
        "Can you get me a cheap flight to Nairobi?",
        "Do I need a visa for Kenya with an Ethiopian passport?",
        "What's scheduled at the Hollywood Bowl this weekend?",
    ],
)
def test_live_facts_ask_the_search_classifier(text: str) -> None:
    assert _live_lookup_cue(text)


@pytest.mark.parametrize(
    "text",
    ["how much is 3 + 4", "what is a derivative", "priceless memories", "her visage"],
)
def test_schoolbook_questions_have_no_live_cue(text: str) -> None:
    assert not _live_lookup_cue(text)


@pytest.mark.parametrize(
    "text",
    [
        "What is the current in a circuit with 12 V across 4 ohms today?",
        "What date is 100 days from tomorrow?",
        "write a text to cancel my haircut at 2pm today",
    ],
)
def test_not_news(text: str) -> None:
    assert not needs_web_search_heuristic(text)


def test_correspondence_requests() -> None:
    assert is_correspondence_request("write a text to cancel my haircut at 2pm today")
    assert is_correspondence_request("can you help me draft an email to my landlord")
    assert not is_correspondence_request("what's the latest news today")


@pytest.mark.parametrize(
    ("text", "named"),
    [
        ("Best Ethiopian restaurant in DC that's open right now?", True),
        ("Get directions to Bole airport from Piassa", True),
        ("What's open near me in Bole?", True),
        ("best pizza in town?", False),
        ("Directions to the airport", False),
        ("coffee near me", False),
        ("In my area, best tacos?", False),
    ],
)
def test_names_its_place(text: str, named: bool) -> None:
    assert names_its_place(text) is named


def test_math_and_code_follow_ups_do_not_search() -> None:
    from app.modules.web_search.detection import _continues_searchable_topic, needs_web_search

    assert not needs_web_search("add 25 and 38 by breaking them into tens and ones")
    assert not _continues_searchable_topic(
        "can you add 12 and 15 the same way?", ["add 25 + 38 by breaking them into tens"]
    )
    assert not _continues_searchable_topic(
        "ok move this into a function", ["scores = [78, 92, 65, 88] why does this print 80.8"]
    )
    assert _continues_searchable_topic(
        "and the red terror martyrs museum?", ["what time does the national museum in addis open"]
    )


def test_a_train_problem_is_not_a_distance_from_the_user() -> None:
    from app.modules.web_search.geo_intent import is_geo_query

    assert not is_geo_query(
        "A train leaves at 9am and travels at 60 km/h. How far has it gone by 11:30am?"
    )
    assert is_geo_query("how far is the airport")


@pytest.mark.parametrize(
    ("text", "geo"),
    [
        # A speed unit glued to its number is still a motion problem.
        ("car doing 90km/h, how far does it go in 4 s in metres", False),
        ("a cyclist rides at 5m/s for 2 minutes how far does she go", False),
        ("A ball is thrown at 30° above the horizontal. how far does it go?", False),
        # A place the season kicked off in is still a trip from the user.
        ("how far is the stadium where they kicked off the season", True),
        ("how far is the nearest pharmacy from me", True),
    ],
)
def test_a_glued_speed_unit_is_motion_and_a_kick_off_is_a_place(text: str, geo: bool) -> None:
    from app.modules.web_search.geo_intent import is_geo_query

    assert is_geo_query(text) is geo


def test_more_live_cues() -> None:
    from app.modules.web_search.detection import needs_web_search

    assert _live_lookup_cue("usd to etb rate rn")
    assert needs_web_search("is it gonna rain tomorrow evening? i have gym at 6pm")
    assert needs_web_search("breaking news from Gaza")
    assert is_correspondence_request("add a line reminding him the rent for this month is paid")


@pytest.mark.parametrize(
    "text",
    [
        "if today is wednesday what day is it in 100 days",
        "whats the next number after the latest one: 2, 6, 18, 54, ...",
        "A news report says 3/5 of the 450 students passed the exam. How many failed?",
        "tomorrows temperature is forecast to be 24°C. what is that in fahrenheit and kelvin?",
        "I water the plants every 3 days and go to the gym every 4 days. if I did both today, "
        "when will I do both on the same day again?",
        "team A scored 3 goals in the first half and twice as many in the second half. "
        "whats the final score",
        "what's new with you",
        "ugh forgot my umbrella today and its pouring",
    ],
)
def test_word_problems_and_small_talk_do_not_search(text: str) -> None:
    from app.modules.web_search.detection import needs_web_search

    assert not needs_web_search(text)


@pytest.mark.parametrize(
    "text",
    [
        "will it rain in 3 days in addis",
        "what's the temperature in addis in fahrenheit today",
        "who won the game last night",
        "what's new in the world",
    ],
)
def test_live_questions_still_search(text: str) -> None:
    from app.modules.web_search.detection import needs_web_search

    assert needs_web_search(text)


@pytest.mark.parametrize(
    "text",
    [
        # How far something moved: the car of the problem before, not the user.
        "how far did it go in that time",
        "how far did it go?",
        "how far will the ball travel",
        "how far did they get before it rained",
        # A walk across or around something takes that thing's length.
        "How long does it take to walk across the Brooklyn Bridge?",
        "how long does it take to walk around Central Park",
        "how long does it take to drive across the US",
        "how long is the walk across the Golden Gate Bridge",
        # Departure and arrival times make the trip length a sum.
        "a bus leaves at 7:15am and arrives at 9:40am how long is the trip",
        "the train departs at 08:10 and arrives in Adama at 10:25. how long is the journey",
        "my flight leaves at 11pm and lands at 6:30am, how long is the flight",
        "I leave at 7:15am and arrive at 9:40am, how long is my commute?",
        # A stated amount converted to another unit.
        "how many miles is a 5k run?",
        "how many km is a half marathon",
        "how many km is 10 miles",
        "how many minutes are in 2.5 hours",
        "how many minutes in a day",
    ],
)
def test_a_trip_the_question_measures_itself_is_not_from_the_user(text: str) -> None:
    from app.modules.web_search.geo_intent import is_distance_query, is_geo_query

    assert not is_distance_query(text)
    assert not is_geo_query(text)


@pytest.mark.parametrize(
    "text",
    [
        "how far is it to the airport",
        "how far is the stadium from here",
        "how long does it take to walk to the station",
        "how long does it take to walk over to my friend's place",
        "how long does it take to drive to the airport",
        # A deadline is not an arrival time.
        "I leave at 5pm and need to arrive by 7pm, how long is the drive?",
        "I leave at 5pm, how long is the drive to the airport?",
        "how long is the trip",
        "how long is the drive",
        "how many miles is it to Hawassa",
        "how many miles is the airport from here",
        "how many minutes is the drive to work",
    ],
)
def test_a_trip_from_the_user_still_needs_their_location(text: str) -> None:
    from app.modules.web_search.geo_intent import is_distance_query

    assert is_distance_query(text)


@pytest.mark.parametrize(
    ("text", "local"),
    [
        # Another world has no forecast and is not where the user is.
        ("whats the weather like on venus", False),
        ("what's the temperature on the moon", False),
        ("weather on mars", False),
        # A named mountain or lake is a place of its own.
        ("what's the weather like on Mount Kenya", False),
        ("what's the weather like on lake tana this weekend", False),
        # A day, the weekend or a birthday is still the user's own weather.
        ("what's the weather like on saturday", True),
        ("what's the weather on the weekend", True),
        ("what's the weather like on my birthday", True),
        ("is it going to rain on sunday", True),
        ("what's the weather like today? also why is venus so hot", True),
    ],
)
def test_weather_on_a_place_or_on_a_day(text: str, local: bool) -> None:
    from app.modules.web_search.geo_intent import is_local_weather_query

    assert is_local_weather_query(text) is local


def test_weather_on_another_world_does_not_search() -> None:
    from app.modules.web_search.detection import needs_web_search

    assert not needs_web_search("whats the weather like on venus")
    assert needs_web_search("what's the weather like on Mount Kenya")


@pytest.mark.parametrize(
    ("text", "named"),
    [
        ("How long does it take to walk across the Brooklyn Bridge?", True),
        ("can we fly over the Grand Canyon", True),
        ("cafes near the Eiffel Tower", True),
        ("how long does it take to walk across the bridge", False),
    ],
)
def test_names_its_place_after_the(text: str, named: bool) -> None:
    assert names_its_place(text) is named


def test_a_forecast_that_also_mentions_a_planet_still_searches() -> None:
    from app.modules.web_search.detection import needs_web_search

    assert needs_web_search("what's the weather tonight? I want to see the rings on saturn")
