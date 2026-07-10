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


def test_quiz_answer_letter():
    assert vocab_quiz_service.quiz_answer_letter("B") == "B"
    assert vocab_quiz_service.quiz_answer_letter("c.") == "C"
    assert vocab_quiz_service.quiz_answer_letter("Is it a?") == "A"
    assert vocab_quiz_service.quiz_answer_letter("I think B") == "B"
    assert vocab_quiz_service.quiz_answer_letter("hello") is None


def test_is_vocab_quiz_answer():
    assert vocab_quiz_service.is_vocab_quiz_answer("Is it a?") is True
    assert vocab_quiz_service.is_vocab_quiz_answer("hello") is False


def test_parse_vocab_quiz_requires_correct_letter():
    fence = (
        "```vocab_quiz\n"
        '{"word":"cat","choices":[{"letter":"A","text":"x"},{"letter":"B","text":"y"}]}\n'
        "```"
    )
    assert vocab_quiz_service.parse_vocab_quiz(fence) is None


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
        grade = await projects_service.apply_deterministic_quiz_answer(
            session,
            user_id=user_id,
            chat_id=uuid.uuid4(),
            project_id=project_id,
            assistant_content=bad_fence,
            user_answer="A",
        )

    assert grade is None


@pytest.mark.asyncio
async def test_apply_deterministic_quiz_answer_skips_without_project_id():
    session = AsyncMock()
    with patch(
        "app.services.projects.projects_repo.get_by_id",
        new=AsyncMock(),
    ) as get_by_id:
        grade = await projects_service.apply_deterministic_quiz_answer(
            session,
            user_id=uuid.uuid4(),
            chat_id=uuid.uuid4(),
            project_id=None,
            assistant_content=TRIVIA_FENCE,
            user_answer="A",
        )
    assert grade is None
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
        patch(
            "app.services.projects.project_items_repo.apply_quiz_result",
            new=AsyncMock(),
        ) as apply_mock,
    ):
        grade = await projects_service.apply_deterministic_quiz_answer(
            session,
            user_id=user_id,
            chat_id=chat_id,
            project_id=project_id,
            assistant_content=TRIVIA_FENCE,
            user_answer="A",
        )

    assert grade is not None
    assert grade.is_correct is True
    assert grade.user_letter == "A"
    assert grade.correct_letter == "A"
    create_mock.assert_awaited_once()
    apply_mock.assert_awaited_once()
    assert apply_mock.await_args.kwargs["is_correct"] is True


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
        patch(
            "app.services.projects.project_items_repo.apply_quiz_result",
            new=AsyncMock(),
        ) as apply_mock,
    ):
        grade = await projects_service.apply_deterministic_quiz_answer(
            session,
            user_id=user_id,
            chat_id=uuid.uuid4(),
            project_id=project_id,
            assistant_content=TRIVIA_FENCE,
            user_answer="B",
        )

    assert grade is not None
    assert grade.is_correct is False
    create_mock.assert_awaited_once()
    apply_mock.assert_awaited_once()
    assert apply_mock.await_args.kwargs["is_correct"] is False
