from app.services.chat.related_prompts import (
    latest_related_prompts,
    related_prompts,
    related_prompts_for_page,
)


def test_arithmetic_question_gets_three_different_related_questions() -> None:
    prompts = related_prompts("what is 1+1?")
    assert prompts == [
        "what is 2+1?",
        "what is 1+2?",
        "what is 1\u22121?",
    ]
    assert "what is 1+1?" not in prompts
    assert len(set(prompts)) == 3


def test_spaced_arithmetic_keeps_the_users_spacing() -> None:
    prompts = related_prompts("What is 1 + 1?")
    assert prompts == [
        "What is 2 + 1?",
        "What is 1 + 2?",
        "What is 1 \u2212 1?",
    ]


def test_numbered_physics_sentence_changes_one_number() -> None:
    text = "what is the force on a 10 kg object accelerating at 3 m/s^2"
    prompts = related_prompts(text)
    assert prompts == [
        "what is the force on a 11 kg object accelerating at 3 m/s^2",
        "what is the force on a 10 kg object accelerating at 4 m/s^2",
        "what is the force on a 12 kg object accelerating at 3 m/s^2",
    ]


def test_numbered_chemistry_sentence_keeps_the_wording() -> None:
    text = "Find molarity of 0.5 mol in 2 L solution"
    prompts = related_prompts(text)
    assert prompts == [
        "Find molarity of 0.6 mol in 2 L solution",
        "Find molarity of 0.5 mol in 3 L solution",
        "Find molarity of 0.7 mol in 2 L solution",
    ]


def test_biology_question_without_a_number_uses_the_topic() -> None:
    prompts = related_prompts("What is photosynthesis?")
    assert prompts == [
        "What is the equation for photosynthesis?",
        "Where does photosynthesis happen?",
        "How is photosynthesis different from cellular respiration?",
    ]


def test_chitchat_has_no_related_prompts() -> None:
    assert related_prompts("how's your day") == []
    assert related_prompts("hi") == []


def test_latest_reply_uses_the_question_just_before_it() -> None:
    prompts = latest_related_prompts(
        [
            ("user", "how's your day"),
            ("assistant", "Pretty good."),
            ("user", "what is 1+1?"),
            ("assistant", "2"),
        ]
    )
    assert prompts[0] == "what is 2+1?"


def test_older_history_page_omits_related_prompts() -> None:
    turns = [("user", "what is 1+1?"), ("assistant", "2")]
    assert related_prompts_for_page(turns, newest_page=False) == []
    assert related_prompts_for_page(turns, newest_page=True)[0] == "what is 2+1?"
