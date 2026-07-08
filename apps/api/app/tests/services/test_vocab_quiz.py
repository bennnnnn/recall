import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.services import projects as projects_service
from app.services import vocab_quiz as vocab_quiz_service

TRIVIA_FENCE = (
    "```vocab_quiz\n"
    '{"quiz_type":"trivia","word":"History",'
    '"question":"Which wonder stood at Rhodes?",'
    '"correct":"A",'
    '"choices":[{"letter":"A","text":"Colossus"},{"letter":"B","text":"Pyramid"}]}\n'
    "```"
)


def test_parse_trivia_quiz_fence():
    quiz = vocab_quiz_service.parse_vocab_quiz(TRIVIA_FENCE)
    assert quiz is not None
    assert quiz.quiz_type == "trivia"
    assert quiz.word == "History"
    assert quiz.question == "Which wonder stood at Rhodes?"
    assert quiz.correct == "A"
    assert quiz.part_of_speech is None


def test_quiz_answer_letter():
    assert vocab_quiz_service.quiz_answer_letter("B") == "B"
    assert vocab_quiz_service.quiz_answer_letter("c.") == "C"
    assert vocab_quiz_service.quiz_answer_letter("hello") is None


def test_parse_vocab_quiz_requires_correct_letter():
    fence = (
        "```vocab_quiz\n"
        '{"word":"cat","choices":[{"letter":"A","text":"x"},{"letter":"B","text":"y"}]}\n'
        "```"
    )
    assert vocab_quiz_service.parse_vocab_quiz(fence) is None


def test_parse_plain_markdown_vocab_quiz_walk():
    content = (
        "**What does walk mean?**\n\n"
        "A) To run very fast\n"
        "B) To move at a regular pace by lifting and setting down each foot\n"
        "C) To sit down\n"
        "D) To jump high"
    )
    quiz = vocab_quiz_service.parse_plain_markdown_vocab_quiz(content)
    assert quiz is not None
    assert quiz.word == "walk"
    assert quiz.choices is not None
    assert "B" in quiz.choices


def test_infer_correct_letter_from_definition_walk():
    choices = {
        "A": "To run very fast",
        "B": "To move at a regular pace by lifting and setting down each foot",
        "C": "To sit down",
        "D": "To jump high",
    }
    definition = "To move at a regular pace by lifting and setting down each foot"
    assert vocab_quiz_service.infer_correct_letter_from_definition(choices, definition) == "B"


def test_grade_quiz_answer_wrong_letter():
    quiz = vocab_quiz_service.ParsedVocabQuiz(
        word="walk",
        part_of_speech="verb",
        question="What does walk mean?",
        correct="B",
        quiz_type="vocab",
        choices={"B": "To move at a regular pace by lifting and setting down each foot"},
    )
    graded = vocab_quiz_service.grade_quiz_answer(quiz, "A")
    assert graded == ("A", "B", False)


@pytest.mark.asyncio
async def test_apply_deterministic_quiz_answer_skips_without_correct():
    from app.models.orm import Project

    session = AsyncMock()
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    project = Project(
        id=project_id,
        user_id=user_id,
        title="General knowledge",
        kind="trivia",
        level="level1",
        target_language="en",
    )
    bad_fence = (
        "```vocab_quiz\n"
        '{"quiz_type":"trivia","word":"History",'
        '"question":"Which wonder stood at Rhodes?",'
        '"choices":[{"letter":"A","text":"Colossus"},{"letter":"B","text":"Pyramid"}]}\n'
        "```"
    )

    with patch(
        "app.services.projects.projects_repo.get_by_id",
        new=AsyncMock(return_value=project),
    ):
        applied = await projects_service.apply_deterministic_quiz_answer(
            session,
            user_id=user_id,
            chat_id=uuid.uuid4(),
            project_id=project_id,
            assistant_content=bad_fence,
            user_answer="A",
        )

    assert applied is False


@pytest.mark.asyncio
async def test_apply_deterministic_quiz_answer_skips_without_project_id():
    session = AsyncMock()
    with patch(
        "app.services.projects.projects_repo.get_by_id",
        new=AsyncMock(),
    ) as get_by_id:
        applied = await projects_service.apply_deterministic_quiz_answer(
            session,
            user_id=uuid.uuid4(),
            chat_id=uuid.uuid4(),
            project_id=None,
            assistant_content=TRIVIA_FENCE,
            user_answer="A",
        )
    assert applied is False
    get_by_id.assert_not_awaited()


def test_strip_vocab_session_metadata():
    content = (
        "🥳 Congratulations!\n\n"
        "```json\n"
        '{"session_complete":true,"words_learned":5,"streak":1}\n'
        "```"
    )
    stripped = vocab_quiz_service.strip_vocab_session_metadata(content)
    assert stripped == "🥳 Congratulations!"
    assert "session_complete" not in stripped


def test_strip_vocab_session_metadata_keeps_unrelated_json():
    content = 'Here is data:\n```json\n{"type":"square","side":5}\n```'
    assert vocab_quiz_service.strip_vocab_session_metadata(content) == content


@pytest.mark.asyncio
async def test_apply_deterministic_quiz_answer_trivia_correct():
    from app.models.orm import Project

    session = AsyncMock()
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    chat_id = uuid.uuid4()
    project = Project(
        id=project_id,
        user_id=user_id,
        title="General knowledge",
        kind="trivia",
        level="level1",
        target_language="en",
        daily_goal=5,
    )

    with (
        patch(
            "app.services.projects.projects_repo.get_by_id",
            new=AsyncMock(return_value=project),
        ),
        patch(
            "app.services.projects.project_items_repo.list_for_user",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.projects.project_items_repo.create",
            new=AsyncMock(),
        ) as create_mock,
    ):
        applied = await projects_service.apply_deterministic_quiz_answer(
            session,
            user_id=user_id,
            chat_id=chat_id,
            project_id=project_id,
            assistant_content=TRIVIA_FENCE,
            user_answer="A",
        )

    assert applied is True
    create_mock.assert_awaited_once()
    kwargs = create_mock.await_args.kwargs
    assert kwargs["content"] == "Which wonder stood at Rhodes?"
    assert kwargs["list_title"] == "History"
    assert kwargs["status"] == "mastered"


@pytest.mark.asyncio
async def test_apply_deterministic_quiz_answer_records_wrong_trivia_as_learning():
    from app.models.orm import Project

    session = AsyncMock()
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    project = Project(
        id=project_id,
        user_id=user_id,
        title="General knowledge",
        kind="trivia",
        level="level1",
        target_language="en",
    )

    with (
        patch(
            "app.services.projects.projects_repo.get_by_id",
            new=AsyncMock(return_value=project),
        ),
        patch(
            "app.services.projects.project_items_repo.list_for_user",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.projects.project_items_repo.create",
            new=AsyncMock(),
        ) as create_mock,
    ):
        applied = await projects_service.apply_deterministic_quiz_answer(
            session,
            user_id=user_id,
            chat_id=uuid.uuid4(),
            project_id=project_id,
            assistant_content=TRIVIA_FENCE,
            user_answer="B",
        )

    assert applied is True
    create_mock.assert_awaited_once()
    assert create_mock.await_args.kwargs["status"] == "learning"
