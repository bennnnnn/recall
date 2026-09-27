from types import SimpleNamespace

import pytest

from app.modules.memory.topics import (
    STANDARD_TOPICS,
    TYPE_DEFAULT_TOPIC,
    area_key,
    fact_topic,
    normalize_topic,
    parse_topic,
    topic_group,
    topic_memory_type,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("tech-stack", "tech-stack"),
        ("  Preferences ", "preferences"),
        ("area:recall", "area:recall"),
        ("area:My Big App!", "area:my-big-app"),
        ("area:", None),
        ("area:!!!", None),
        ("hobbies", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_topic_accepts_standard_keys_and_areas_only(raw, expected):
    assert parse_topic(raw) == expected


def test_normalize_topic_falls_back_to_the_type_default():
    assert normalize_topic("hobbies", memory_type="preference") == "preferences"
    assert normalize_topic(None, memory_type="project") == "side-projects"
    assert normalize_topic("area:africana", memory_type="fact") == "area:africana"


def test_area_key_slugs_and_caps_the_name():
    assert area_key("Africana — diaspora app") == "area:africana-diaspora-app"
    long_key = area_key("x" * 100)
    assert long_key is not None
    assert len(long_key) == len("area:") + 40


@pytest.mark.parametrize(
    "topic,memory_type,group",
    [
        ("profile", "profile", "you"),
        ("preferences", "preference", "you"),
        ("tech-stack", "fact", "topics"),
        ("recent-work", "focus", "topics"),
        ("side-projects", "project", "topics"),
        ("area:recall", "project", "areas"),
    ],
)
def test_topic_decides_type_and_group(topic, memory_type, group):
    assert topic_memory_type(topic) == memory_type
    assert topic_group(topic) == group


def test_every_type_default_is_a_standard_topic_of_that_type():
    keys = {spec.key for spec in STANDARD_TOPICS}
    for memory_type, topic in TYPE_DEFAULT_TOPIC.items():
        assert topic in keys
        assert topic_memory_type(topic) == memory_type


def test_fact_topic_uses_the_stored_topic_or_the_type_default():
    assert fact_topic(SimpleNamespace(topic="area:recall", type="project")) == "area:recall"
    assert fact_topic(SimpleNamespace(topic=None, type="preference")) == "preferences"
