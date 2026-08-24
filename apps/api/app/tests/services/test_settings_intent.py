import pytest

from app.services.settings_intent import extract_settings_changes


@pytest.mark.parametrize(
    ("text", "field", "value"),
    [
        ("switch to dark mode", "appearance", "dark"),
        ("use light theme", "appearance", "light"),
        ("change appearance to system", "appearance", "system"),
        ("switch to default theme", "appearance", "system"),
        ("set appearance to default", "appearance", "system"),
        ("dark mode", "appearance", "dark"),
        ("use pro", "default_model", "smart-chat"),
        ("switch to flash", "default_model", "free-chat"),
        ("switch the model to GPT", "default_model", "gpt-5.5"),
        ("use auto", "default_model", "auto"),
        ("be more professional", "response_tone", "professional"),
        ("be funnier", "response_tone", "funny"),
        ("make it casual", "response_tone", "casual"),
        ("softer tone", "response_tone", "soft"),
        ("switch language to Spanish", "locale", "es"),
        ("change language to French", "locale", "fr"),
        ("set language to de", "locale", "de"),
    ],
)
def test_extracts_allowlisted_settings(text: str, field: str, value: str) -> None:
    changes = extract_settings_changes(text)
    assert len(changes) == 1
    assert changes[0].field == field
    assert changes[0].value == value


@pytest.mark.parametrize(
    "text",
    [
        "write a professional email",
        "explain dark matter",
        "tell me a funny story",
        "what time is my flight",
        "draft a casual message to mom",
        "how does photosynthesis work",
        "Spanish civil war",
        "use max",
    ],
)
def test_ignores_content_requests(text: str) -> None:
    assert extract_settings_changes(text) == []


def test_can_extract_two_allowlisted_changes() -> None:
    changes = extract_settings_changes("switch to dark mode and be more professional")
    fields = {item.field: item.value for item in changes}
    assert fields["appearance"] == "dark"
    assert fields["response_tone"] == "professional"
