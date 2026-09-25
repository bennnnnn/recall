from app.modules.memory.self_facts import stated_self_facts


def test_working_on_project_is_a_memory() -> None:
    found = stated_self_facts("User: I am working on a chemistry solver")
    assert found == [
        ("project", "User is working on a chemistry solver", "a chemistry solver"),
    ]


def test_im_working_on_cuts_the_help_request() -> None:
    found = stated_self_facts("I'm working on Recall, can you help me debug the build?")
    assert len(found) == 1
    assert found[0][0] == "project"
    assert found[0][2] == "Recall"


def test_story_character_working_on_is_not_the_user() -> None:
    assert stated_self_facts("Bebe is working on a chemistry solver") == []


def test_pronoun_and_problem_are_not_projects() -> None:
    assert stated_self_facts("I am working on it") == []
    assert stated_self_facts("I am working on the problem Bebe has 2 pens") == []


def test_assistant_line_is_ignored() -> None:
    transcript = "Assistant: You are working on a secret project\nUser: thanks"
    assert stated_self_facts(transcript) == []
