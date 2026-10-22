import pytest

from app.models import model_catalog
from app.modules.account.settings_intent import SettingsChange, extract_settings_changes


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
        ("switch the model to GPT", "default_model", "gpt-6-luna"),
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
        "Make a 4-week plan to learn Spanish. How do I start.",
        "Give me a 4-week plan to learn Spanish for travel.",
    ],
)
def test_ignores_content_requests(text: str) -> None:
    assert extract_settings_changes(text) == []


def test_can_extract_two_allowlisted_changes() -> None:
    changes = extract_settings_changes("switch to dark mode and be more professional")
    fields = {item.field: item.value for item in changes}
    assert fields["appearance"] == "dark"
    assert fields["response_tone"] == "professional"


@pytest.mark.parametrize(
    "text",
    [
        "Make it less formal.",
        "Now make it professional.",
        "Make this version casual.",
    ],
)
def test_referential_tone_change_revises_prior_message_draft(text: str) -> None:
    prior = "```message\nHi Sam, I will be 20 minutes late.\n```"

    assert extract_settings_changes(text, prior_assistant=prior) == []


def test_explicit_setting_change_still_wins_after_message_draft() -> None:
    prior = "```message\nHi Sam, I will be 20 minutes late.\n```"

    changes = extract_settings_changes(
        "Set my app preference to professional.", prior_assistant=prior
    )

    assert changes == [SettingsChange("response_tone", "professional")]


# Found by the behavior sweep: questions and edits of the last reply changed settings.
@pytest.mark.parametrize(
    "text",
    [
        "Is the pro model worth it?",
        "dark mode vs light mode — which is better for your eyes?",
        "should I use dark mode at night?",
        "which model is faster?",
        "rewrite this paragraph in Spanish",
        "make the email's tone more formal",
    ],
)
def test_questions_and_content_edits_are_not_settings(text: str) -> None:
    assert extract_settings_changes(text) == []


def test_make_it_after_any_reply_edits_that_reply() -> None:
    prior = "Happy 60th birthday, Dad! Thank you for everything you do."
    assert extract_settings_changes("make it funnier", prior_assistant=prior) == []
    assert extract_settings_changes("make your replies funnier", prior_assistant=prior) == [
        SettingsChange("response_tone", "funny")
    ]
    assert extract_settings_changes("switch it to dark mode", prior_assistant=prior) == [
        SettingsChange("appearance", "dark")
    ]


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("reply in Amharic from now on", "am"),
        ("answer in Spanish from now on", "es"),
        ("always reply in French", "fr"),
    ],
)
def test_from_now_on_sets_the_language(text: str, value: str) -> None:
    assert extract_settings_changes(text) == [SettingsChange("locale", value)]


@pytest.mark.parametrize("text", ["reply in Amharic", "translate this to Spanish from now on"])
def test_one_answer_in_a_language_is_not_a_setting(text: str) -> None:
    assert extract_settings_changes(text) == []


def test_more_questions_edits_and_system_theme() -> None:
    assert extract_settings_changes("light mode or dark mode for reading at night?") == []
    assert (
        extract_settings_changes(
            "ok i'll call mom tonight, can you make the opening softer?",
            prior_assistant="Opening: Mom, I have news.",
        )
        == []
    )
    assert extract_settings_changes("make the app theme follow my phone's setting") == [
        SettingsChange("appearance", "system")
    ]
    assert extract_settings_changes("can you switch to dark mode?") == [
        SettingsChange("appearance", "dark")
    ]


@pytest.mark.parametrize(
    ("text", "prior", "expected"),
    [
        ("the light mode on my phone hurts my eyes", None, []),
        ("birthday wishes for my boss, professional but warm", None, []),
        (
            "set the tone to warm",
            "Dear Tsehay,\n\nThank you so much for looking after the cat!",
            [],
        ),
        (
            "switch to dark mode pls, writing in bed and the screen is blinding",
            None,
            [SettingsChange("appearance", "dark")],
        ),
        (
            "from now on i want warmer replies, change my tone setting to warm",
            None,
            [SettingsChange("response_tone", "soft")],
        ),
        (
            "from now on talk to me in a more casual tone",
            None,
            [SettingsChange("response_tone", "casual")],
        ),
    ],
)
def test_long_lines_need_an_ask_and_a_verb(text, prior, expected) -> None:
    assert extract_settings_changes(text, prior_assistant=prior) == expected


def _model_named(text: str) -> str | None:
    changes = extract_settings_changes(text)
    return changes[0].value if [c.field for c in changes] == ["default_model"] else None


def test_every_model_in_the_picker_can_be_named_in_chat() -> None:
    # The reader's words come from the catalog (code-health audit ARCH-06): a model
    # added there is reachable by its id and by the label Settings → Models shows.
    for model in model_catalog.selectable_models():
        assert _model_named(f"switch to {model.id}") == model.id
        assert _model_named(f"switch to {model.label}") == model.id, model.label


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("switch to GLM", "glm-5.3-flash"),
        ("switch to glm 5.2", "glm-5.2"),
        ("use GLM 5.3 Flash", "glm-5.3-flash"),
        ("use deepseek", "smart-chat"),
        ("switch to Claude", "free-chat"),
        ("claude model please", "free-chat"),
        ("use chatgpt", "gpt-6-luna"),
    ],
)
def test_a_brand_names_its_model_and_a_version_picks_one(text: str, value: str) -> None:
    assert _model_named(text) == value


@pytest.mark.parametrize(
    "text",
    [
        "change my name to Claude",
        "call me Claude",
        "set my nickname to Claude please",
        "my friend claude is visiting, use a warm tone",
    ],
)
def test_a_brand_that_is_also_a_name_is_read_as_a_name(text: str) -> None:
    assert all(change.field != "default_model" for change in extract_settings_changes(text))
