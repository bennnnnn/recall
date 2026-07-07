"""Tests for pre-generated daily quiz batches."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.repositories import project_quiz_questions as quiz_repo
from app.services import project_daily_quiz as daily_quiz_service


def _question(**overrides):
    base = dict(
        id=uuid4(),
        status="pending",
        quiz_kind="vocab",
        topic="apple",
        quiz_date=date.today(),
        sequence=0,
        question_text='What does "apple" mean?',
        choices=[
            {"letter": "A", "text": "wrong"},
            {"letter": "B", "text": "a fruit"},
            {"letter": "C", "text": "also wrong"},
            {"letter": "D", "text": "nope"},
        ],
        correct_letter="B",
        reference_definition="a fruit",
        part_of_speech="noun",
        project_item_id=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _language_project(project_id=None):
    return SimpleNamespace(
        id=project_id or uuid4(),
        kind="language",
        level="level1",
        title="English",
        description="",
        daily_goal=5,
    )


def test_normalize_topic_casefold():
    assert quiz_repo.normalize_topic("Apple") == "apple"


def test_mock_vocab_questions_from_pool():
    items = [
        SimpleNamespace(
            id=uuid4(),
            content="apple",
            part_of_speech="noun",
            definition="a fruit",
            status="new",
        )
    ]
    questions = daily_quiz_service._mock_vocab_questions(items, 1)
    assert len(questions) == 1
    assert questions[0].topic == "apple"
    assert questions[0].correct == "B"
    assert len(questions[0].choices) == 4


def test_mock_trivia_questions():
    project = SimpleNamespace(
        id=uuid4(),
        kind="trivia",
        description="History, Science",
    )
    questions = daily_quiz_service._mock_trivia_questions(project, 2)
    assert len(questions) == 2
    assert questions[0].topic == "History"
    assert questions[1].topic == "Science"


def test_mock_trivia_questions_reuses_categories():
    project = SimpleNamespace(
        id=uuid4(),
        kind="trivia",
        description="history,science",
    )
    questions = daily_quiz_service._mock_trivia_questions(project, 5)
    assert len(questions) == 5
    assert questions[0].topic == "History"
    assert questions[2].topic == "History"
    assert all(q.correct == "B" for q in questions)


@pytest.mark.asyncio
async def test_generate_trivia_batch_inserts_all_questions():
    session = AsyncMock()
    user_id = uuid4()
    project = SimpleNamespace(
        id=uuid4(),
        kind="trivia",
        description="history,science",
    )
    quiz_date = date.today()
    inserted: list[int] = []

    async def fake_insert(*_args, **kwargs):
        inserted.append(kwargs["sequence"])
        return SimpleNamespace(id=uuid4(), **kwargs)

    with (
        patch.object(
            daily_quiz_service.quiz_questions_repo,
            "list_for_project_date",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            daily_quiz_service.quiz_questions_repo,
            "insert_question",
            AsyncMock(side_effect=fake_insert),
        ),
        patch(
            "app.services.project_daily_quiz.should_mock_llm",
            return_value=True,
        ),
    ):
        await daily_quiz_service._generate_trivia_batch(
            session,
            Settings(),
            user_id=user_id,
            project=project,
            quiz_date=quiz_date,
            count=5,
        )

    assert inserted == [0, 1, 2, 3, 4]


def test_mock_new_vocab_words_skips_duplicates():
    words = daily_quiz_service._mock_new_vocab_words(2, existing={"word1"})
    assert len(words) == 2
    assert words[0].content == "word2"
    assert words[1].content == "word3"


@pytest.mark.asyncio
async def test_get_daily_quiz_returns_current_question():
    session = AsyncMock()
    user_id = uuid4()
    project_id = uuid4()
    project = _language_project(project_id)
    row = _question()

    with (
        patch.object(
            daily_quiz_service.projects_repo,
            "get_by_id",
            AsyncMock(return_value=project),
        ),
        patch.object(
            daily_quiz_service.quiz_questions_repo,
            "count_answered_today",
            AsyncMock(return_value=0),
        ),
        patch.object(
            daily_quiz_service.quiz_questions_repo,
            "next_pending",
            AsyncMock(return_value=row),
        ),
    ):
        result = await daily_quiz_service.get_daily_quiz(
            session,
            user_id=user_id,
            project_id=project_id,
            timezone_name="UTC",
        )

    assert result is not None
    assert result.current is not None
    assert result.current.topic == "apple"
    assert result.daily_goal == 5


@pytest.mark.asyncio
async def test_get_daily_quiz_not_complete_when_goal_unmet():
    session = AsyncMock()
    user_id = uuid4()
    project_id = uuid4()
    project = _language_project(project_id)

    with (
        patch.object(
            daily_quiz_service.projects_repo,
            "get_by_id",
            AsyncMock(return_value=project),
        ),
        patch.object(
            daily_quiz_service.quiz_questions_repo,
            "count_answered_today",
            AsyncMock(return_value=2),
        ),
        patch.object(
            daily_quiz_service.quiz_questions_repo,
            "next_pending",
            AsyncMock(return_value=None),
        ),
    ):
        result = await daily_quiz_service.get_daily_quiz(
            session,
            user_id=user_id,
            project_id=project_id,
            timezone_name="UTC",
        )

    assert result is not None
    assert result.complete is False
    assert result.current is None
    assert result.answered_count == 2


@pytest.mark.asyncio
async def test_get_daily_quiz_hides_current_when_goal_met():
    session = AsyncMock()
    user_id = uuid4()
    project_id = uuid4()
    project = _language_project(project_id)
    row = _question()

    with (
        patch.object(
            daily_quiz_service.projects_repo,
            "get_by_id",
            AsyncMock(return_value=project),
        ),
        patch.object(
            daily_quiz_service.quiz_questions_repo,
            "count_answered_today",
            AsyncMock(return_value=5),
        ),
        patch.object(
            daily_quiz_service.quiz_questions_repo,
            "next_pending",
            AsyncMock(return_value=row),
        ),
    ):
        result = await daily_quiz_service.get_daily_quiz(
            session,
            user_id=user_id,
            project_id=project_id,
            timezone_name="UTC",
        )

    assert result is not None
    assert result.complete is True
    assert result.current is None


@pytest.mark.asyncio
async def test_ensure_daily_quiz_backfills_when_batch_exhausted_before_goal():
    session = AsyncMock()
    user_id = uuid4()
    project_id = uuid4()
    project = _language_project(project_id)
    row = _question()

    with (
        patch.object(
            daily_quiz_service.projects_repo,
            "get_by_id",
            AsyncMock(return_value=project),
        ),
        patch.object(
            daily_quiz_service.quiz_questions_repo,
            "count_answered_today",
            AsyncMock(return_value=2),
        ),
        patch.object(
            daily_quiz_service.quiz_questions_repo,
            "count_pending_today",
            AsyncMock(return_value=0),
        ),
        patch.object(
            daily_quiz_service,
            "purge_legacy_placeholder_pending",
            AsyncMock(return_value=0),
        ),
        patch.object(
            daily_quiz_service,
            "_top_up_pending_questions",
            AsyncMock(return_value=True),
        ) as top_up,
        patch.object(
            daily_quiz_service.quiz_questions_repo,
            "next_pending",
            AsyncMock(return_value=row),
        ),
        patch.object(session, "commit", AsyncMock()),
    ):
        result = await daily_quiz_service.ensure_daily_quiz(
            session,
            Settings(),
            user_id=user_id,
            project_id=project_id,
            timezone_name="UTC",
        )

    top_up.assert_awaited_once()
    assert result is not None
    assert result.complete is False
    assert result.current is not None


@pytest.mark.asyncio
async def test_submit_answer_skip_advances():
    session = AsyncMock()
    user_id = uuid4()
    project_id = uuid4()
    project = _language_project(project_id)
    question = _question()
    next_row = _question(topic="banana", sequence=1)

    with (
        patch.object(
            daily_quiz_service.projects_repo,
            "get_by_id",
            AsyncMock(return_value=project),
        ),
        patch.object(
            daily_quiz_service.quiz_questions_repo,
            "get_by_id",
            AsyncMock(return_value=question),
        ),
        patch.object(
            daily_quiz_service.quiz_questions_repo,
            "mark_answered",
            AsyncMock(return_value=question),
        ),
        patch.object(
            daily_quiz_service.quiz_questions_repo,
            "count_answered_today",
            AsyncMock(return_value=0),
        ),
        patch.object(
            daily_quiz_service.quiz_questions_repo,
            "next_pending",
            AsyncMock(return_value=next_row),
        ),
    ):
        result = await daily_quiz_service.submit_answer(
            session,
            Settings(),
            user_id=user_id,
            project_id=project_id,
            question_id=question.id,
            modality="mcq",
            letter=None,
            text=None,
            timezone_name="UTC",
            skip=True,
        )

    assert result is not None
    assert result.is_correct is False
    assert "Skipped" in result.feedback
    assert result.next_question is not None
    assert result.next_question.topic == "banana"


@pytest.mark.asyncio
async def test_submit_answer_mcq_correct_mock():
    session = AsyncMock()
    user_id = uuid4()
    project_id = uuid4()
    project = _language_project(project_id)
    question = _question()

    with (
        patch.object(
            daily_quiz_service.projects_repo,
            "get_by_id",
            AsyncMock(return_value=project),
        ),
        patch.object(
            daily_quiz_service.quiz_questions_repo,
            "get_by_id",
            AsyncMock(return_value=question),
        ),
        patch.object(
            daily_quiz_service.quiz_questions_repo,
            "mark_answered",
            AsyncMock(return_value=question),
        ),
        patch.object(
            daily_quiz_service.quiz_questions_repo,
            "count_answered_today",
            AsyncMock(return_value=1),
        ),
        patch.object(
            daily_quiz_service,
            "_next_pending_question",
            AsyncMock(return_value=None),
        ),
        patch.object(
            daily_quiz_service,
            "_apply_mastery",
            AsyncMock(return_value=True),
        ),
    ):
        result = await daily_quiz_service.submit_answer(
            session,
            Settings(),
            user_id=user_id,
            project_id=project_id,
            question_id=question.id,
            modality="mcq",
            letter="B",
            text=None,
            timezone_name="UTC",
        )

    assert result is not None
    assert result.is_correct is True
    assert "correct" in result.feedback.lower()
    assert result.mastered is True


@pytest.mark.asyncio
async def test_submit_answer_definition_wrong_allows_retry():
    session = AsyncMock()
    user_id = uuid4()
    project_id = uuid4()
    project = _language_project(project_id)
    question = _question()

    with (
        patch.object(
            daily_quiz_service.projects_repo,
            "get_by_id",
            AsyncMock(return_value=project),
        ),
        patch.object(
            daily_quiz_service.quiz_questions_repo,
            "get_by_id",
            AsyncMock(return_value=question),
        ),
        patch.object(
            daily_quiz_service,
            "_grade_free_text",
            AsyncMock(
                return_value=daily_quiz_service._GradeResult(
                    is_correct=False,
                    feedback="Not quite — try again.",
                    allow_retry=True,
                )
            ),
        ),
        patch.object(
            daily_quiz_service.quiz_questions_repo,
            "count_answered_today",
            AsyncMock(return_value=0),
        ),
        patch.object(
            daily_quiz_service.quiz_questions_repo,
            "next_pending",
            AsyncMock(return_value=None),
        ),
    ):
        result = await daily_quiz_service.submit_answer(
            session,
            Settings(),
            user_id=user_id,
            project_id=project_id,
            question_id=question.id,
            modality="definition",
            letter=None,
            text="something wrong",
            timezone_name="UTC",
        )

    assert result is not None
    assert result.allow_retry is True
    assert result.suggest_mcq is True
    assert result.next_question is not None
    assert result.next_question.topic == "apple"


@pytest.mark.asyncio
async def test_provision_new_vocab_words_adds_items():
    session = AsyncMock()
    session.add = lambda item: None
    session.flush = AsyncMock()
    user_id = uuid4()
    project = _language_project()
    items: list[SimpleNamespace] = []
    pool: list[SimpleNamespace] = []

    with patch(
        "app.services.project_daily_quiz.should_mock_llm",
        return_value=True,
    ):
        updated = await daily_quiz_service._provision_new_vocab_words(
            session,
            Settings(),
            user_id=user_id,
            project=project,
            items=items,
            pool=pool,
            count=2,
        )

    assert len(updated) == 2
    assert len(pool) == 2
    assert updated[0].content == "word1"
    assert updated[0].status == "new"


@pytest.mark.asyncio
async def test_ensure_daily_quiz_generates_when_batch_missing():
    session = AsyncMock()
    user_id = uuid4()
    project_id = uuid4()
    project = _language_project(project_id)
    row = _question()

    with (
        patch.object(
            daily_quiz_service.projects_repo,
            "get_by_id",
            AsyncMock(return_value=project),
        ),
        patch.object(
            daily_quiz_service.quiz_questions_repo,
            "count_answered_today",
            AsyncMock(return_value=0),
        ),
        patch.object(
            daily_quiz_service.quiz_questions_repo,
            "count_pending_today",
            AsyncMock(return_value=0),
        ),
        patch.object(
            daily_quiz_service,
            "purge_legacy_placeholder_pending",
            AsyncMock(return_value=0),
        ),
        patch.object(
            daily_quiz_service,
            "_top_up_pending_questions",
            AsyncMock(return_value=True),
        ) as top_up,
        patch.object(
            daily_quiz_service.quiz_questions_repo,
            "next_pending",
            AsyncMock(return_value=row),
        ),
        patch.object(session, "commit", AsyncMock()),
    ):
        result = await daily_quiz_service.ensure_daily_quiz(
            session,
            Settings(),
            user_id=user_id,
            project_id=project_id,
            timezone_name="UTC",
        )

    top_up.assert_awaited_once()
    assert result is not None
    assert result.current is not None


@pytest.mark.asyncio
async def test_explain_mcq_mock_incorrect():
    question = _question()
    with patch("app.services.project_daily_quiz.should_mock_llm", return_value=True):
        feedback = await daily_quiz_service._explain_mcq(
            Settings(),
            question,
            "A",
            is_correct=False,
        )
    assert "Not quite" in feedback
    assert "B" in feedback


def test_template_mcq_feedback_skips_placeholder_explanation():
    question = _question()
    question.quiz_kind = "trivia"
    question.topic = "History"
    question.reference_definition = "Correct answer"
    feedback = daily_quiz_service._template_mcq_feedback(question, "D", is_correct=False)
    assert feedback == "Not quite — **B** is correct.\n\na fruit"


def test_template_mcq_feedback_includes_reference_fact():
    question = _question()
    question.quiz_kind = "trivia"
    question.reference_definition = "The Colossus stood at the harbor of Rhodes."
    feedback = daily_quiz_service._template_mcq_feedback(question, "A", is_correct=False)
    assert "Colossus" in feedback


def test_is_legacy_placeholder_question_detects_sample_rows():
    question = _question()
    question.question_text = "Sample Geography question #3?"
    question.choices = [
        {"letter": "A", "text": "Wrong answer"},
        {"letter": "B", "text": "Correct answer"},
        {"letter": "C", "text": "Another wrong"},
        {"letter": "D", "text": "Also wrong"},
    ]
    assert daily_quiz_service._is_legacy_placeholder_question(question) is True


@pytest.mark.asyncio
async def test_purge_legacy_placeholder_pending():
    session = AsyncMock()
    project_id = uuid4()
    stale = _question()
    stale.question_text = "Sample Science question #1?"
    stale.choices = [
        {"letter": "A", "text": "Wrong answer"},
        {"letter": "B", "text": "Correct answer"},
        {"letter": "C", "text": "Another wrong"},
        {"letter": "D", "text": "Also wrong"},
    ]
    fresh = _question(topic="Science")
    fresh.question_text = "What is the chemical symbol for water?"

    with (
        patch.object(
            daily_quiz_service.quiz_questions_repo,
            "list_pending_for_date",
            AsyncMock(return_value=[stale, fresh]),
        ),
        patch.object(
            daily_quiz_service.quiz_questions_repo,
            "delete_pending_by_ids",
            AsyncMock(return_value=1),
        ) as delete_mock,
    ):
        removed = await daily_quiz_service.purge_legacy_placeholder_pending(
            session, project_id, date.today()
        )

    assert removed == 1
    delete_mock.assert_awaited_once()
    deleted_ids = delete_mock.await_args.args[3]
    assert stale.id in deleted_ids


@pytest.mark.asyncio
async def test_top_up_pending_generates_one_question():
    session = AsyncMock()
    user_id = uuid4()
    project_id = uuid4()
    project = _language_project(project_id)

    with (
        patch.object(
            daily_quiz_service.quiz_questions_repo,
            "count_answered_today",
            AsyncMock(return_value=1),
        ),
        patch.object(
            daily_quiz_service.quiz_questions_repo,
            "count_pending_today",
            AsyncMock(side_effect=[0, 1]),
        ),
        patch.object(
            daily_quiz_service,
            "purge_legacy_placeholder_pending",
            AsyncMock(return_value=0),
        ),
        patch.object(
            daily_quiz_service,
            "_generate_batch",
            AsyncMock(),
        ) as generate,
    ):
        added = await daily_quiz_service._top_up_pending_questions(
            session,
            Settings(),
            user_id=user_id,
            project=project,
            quiz_date=date.today(),
        )

    assert added is True
    generate.assert_awaited_once()
    assert generate.await_args.kwargs["count"] == 1
