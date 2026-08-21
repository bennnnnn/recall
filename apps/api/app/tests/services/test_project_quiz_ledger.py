import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.services import projects as projects_service

VOCAB_FENCE = (
    "```vocab_quiz\n"
    '{"word":"apple","question":"What does it mean?",'
    '"correct":"A",'
    '"choices":['
    '{"letter":"A","text":"fruit"},'
    '{"letter":"B","text":"car"},'
    '{"letter":"C","text":"place"},'
    '{"letter":"D","text":"animal"}'
    "]}\n"
    "```"
)


@pytest.mark.asyncio
async def test_apply_deterministic_quiz_answer_records_wrong_vocab_as_learning():
    from app.models.orm import Project, ProjectItem

    session = AsyncMock()
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    project = Project(
        id=project_id,
        user_id=user_id,
        title="English",
        kind="language",
        level="level2",
        target_language="en",
    )
    existing = ProjectItem(
        id=uuid.uuid4(),
        user_id=user_id,
        project_id=project_id,
        content="apple",
        list_title="General",
        status="learning",
        quiz_attempts=1,
        quiz_correct=0,
        review_count=0,
        ease_factor=2.5,
        interval_days=0,
    )

    with (
        patch(
            "app.repositories.projects.get_by_id",
            new=AsyncMock(return_value=project),
        ),
        patch(
            "app.repositories.project_items.find_quiz_candidates",
            new=AsyncMock(return_value=[existing]),
        ),
        patch(
            "app.services.projects.quiz_grading.apply_quiz_result",
            new=AsyncMock(return_value=existing),
        ) as apply_mock,
        # Keep the fence's correct=A — verified_correct_letter can call the
        # (mock) LLM; disagreement is advisory only and does not block persist.
        patch(
            "app.services.vocab_quiz.verified_correct_letter",
            new=AsyncMock(return_value=None),
        ),
    ):
        grade = await projects_service.apply_deterministic_quiz_answer(
            session,
            user_id=user_id,
            chat_id=uuid.uuid4(),
            project_id=project_id,
            assistant_content=VOCAB_FENCE,
            user_answer="B",
            attempt=3,
        )

    assert grade is not None
    assert grade.is_correct is False
    assert grade.tries_exhausted is True
    apply_mock.assert_awaited_once()
    assert apply_mock.await_args.kwargs["is_correct"] is False
    assert apply_mock.await_args.kwargs["commit"] is False
    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_deterministic_quiz_answer_rolls_back_failed_ledger_write():
    from app.models.orm import Project, ProjectItem

    session = AsyncMock()
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    project = Project(
        id=project_id,
        user_id=user_id,
        title="English",
        kind="language",
        level="level2",
        target_language="en",
    )
    existing = ProjectItem(
        id=uuid.uuid4(),
        user_id=user_id,
        project_id=project_id,
        content="apple",
        list_title="General",
        status="learning",
        quiz_attempts=0,
        quiz_correct=0,
        review_count=0,
        ease_factor=2.5,
        interval_days=0,
    )

    with (
        patch("app.repositories.projects.get_by_id", AsyncMock(return_value=project)),
        patch(
            "app.repositories.project_items.find_quiz_candidates",
            AsyncMock(return_value=[existing]),
        ),
        patch(
            "app.services.projects.quiz_grading.apply_quiz_result",
            AsyncMock(side_effect=RuntimeError("ledger failed")),
        ) as apply_mock,
        patch(
            "app.services.vocab_quiz.verified_correct_letter",
            AsyncMock(return_value="A"),
        ),
    ):
        with pytest.raises(RuntimeError, match="ledger failed"):
            await projects_service.apply_deterministic_quiz_answer(
                session,
                user_id=user_id,
                chat_id=uuid.uuid4(),
                project_id=project_id,
                assistant_content=VOCAB_FENCE,
                user_answer="A",
            )

    assert apply_mock.await_args.kwargs["commit"] is False
    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_apply_deterministic_verifier_disagreement_still_persists():
    """A second-opinion mismatch is advisory only — always persist on the fence key.

    The verifier was added to catch bad cards, not to override the user-visible
    answer key. Abstaining drops progress (LANG-GRAD-001/002) with no recovery
    path. The grade returned to the model still uses quiz.correct.
    """
    from app.models.orm import Project, ProjectItem

    session = AsyncMock()
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    project = Project(
        id=project_id,
        user_id=user_id,
        title="English",
        kind="language",
        level="level2",
        target_language="en",
    )
    existing = ProjectItem(
        id=uuid.uuid4(),
        user_id=user_id,
        project_id=project_id,
        content="apple",
        list_title="General",
        status="learning",
        quiz_attempts=1,
        quiz_correct=0,
        review_count=0,
        ease_factor=2.5,
        interval_days=0,
    )

    with (
        patch(
            "app.repositories.projects.get_by_id",
            new=AsyncMock(return_value=project),
        ),
        patch(
            "app.repositories.project_items.find_quiz_candidates",
            new=AsyncMock(return_value=[existing]),
        ),
        patch(
            "app.services.projects.quiz_grading.apply_quiz_result",
            new=AsyncMock(return_value=existing),
        ) as apply_mock,
        patch(
            "app.services.vocab_quiz.verified_correct_letter",
            new=AsyncMock(return_value="C"),
        ),
    ):
        grade = await projects_service.apply_deterministic_quiz_answer(
            session,
            user_id=user_id,
            chat_id=uuid.uuid4(),
            project_id=project_id,
            assistant_content=VOCAB_FENCE,
            user_answer="A",
            attempt=1,
        )

    assert grade is not None
    assert grade.is_correct is True
    assert grade.correct_letter == "A"
    # Verifier disagreement is advisory — still persist on the fence key.
    apply_mock.assert_awaited_once()
    assert apply_mock.await_args.kwargs["is_correct"] is True


@pytest.mark.asyncio
async def test_apply_deterministic_verifier_agreement_persists():
    from app.models.orm import Project, ProjectItem

    session = AsyncMock()
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    project = Project(
        id=project_id,
        user_id=user_id,
        title="English",
        kind="language",
        level="level2",
        target_language="en",
    )
    existing = ProjectItem(
        id=uuid.uuid4(),
        user_id=user_id,
        project_id=project_id,
        content="apple",
        list_title="General",
        status="learning",
        quiz_attempts=1,
        quiz_correct=0,
        review_count=0,
        ease_factor=2.5,
        interval_days=0,
    )

    with (
        patch(
            "app.repositories.projects.get_by_id",
            new=AsyncMock(return_value=project),
        ),
        patch(
            "app.repositories.project_items.find_quiz_candidates",
            new=AsyncMock(return_value=[existing]),
        ),
        patch(
            "app.services.projects.quiz_grading.apply_quiz_result",
            new=AsyncMock(return_value=existing),
        ) as apply_mock,
        patch(
            "app.services.vocab_quiz.verified_correct_letter",
            new=AsyncMock(return_value="A"),
        ),
    ):
        grade = await projects_service.apply_deterministic_quiz_answer(
            session,
            user_id=user_id,
            chat_id=uuid.uuid4(),
            project_id=project_id,
            assistant_content=VOCAB_FENCE,
            user_answer="A",
            attempt=1,
        )

    assert grade is not None
    assert grade.is_correct is True
    assert grade.correct_letter == "A"
    apply_mock.assert_awaited_once()
    assert apply_mock.await_args.kwargs["is_correct"] is True


@pytest.mark.asyncio
async def test_apply_deterministic_records_wrong_attempt_without_sm2():
    """LANG-TEACH-011: Wrong answers on tries 1-2 should still record the
    attempt (increment quiz_attempts, set last_incorrect_at, log miss event)
    so missed_today counts them toward the daily goal — but without SM-2
    scheduling (ease_factor/interval/due_at unchanged)."""
    from app.models.orm import Project, ProjectItem

    session = AsyncMock()
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    project = Project(
        id=project_id,
        user_id=user_id,
        title="English",
        kind="language",
        level="level2",
        target_language="en",
    )
    existing = ProjectItem(
        id=uuid.uuid4(),
        user_id=user_id,
        project_id=project_id,
        content="apple",
        list_title="General",
        status="learning",
        quiz_attempts=0,
        quiz_correct=0,
        review_count=0,
        ease_factor=2.5,
        interval_days=0,
    )
    session.add = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()

    with (
        patch(
            "app.repositories.projects.get_by_id",
            new=AsyncMock(return_value=project),
        ),
        patch(
            "app.repositories.project_items.find_quiz_candidates",
            new=AsyncMock(return_value=[existing]),
        ),
        patch(
            "app.services.projects.quiz_grading.apply_quiz_result",
            new=AsyncMock(),
        ) as apply_mock,
        patch(
            "app.repositories.project_items.record_quiz_attempt",
            new=AsyncMock(),
        ) as record_mock,
        patch(
            "app.services.vocab_quiz.verified_correct_letter",
            new=AsyncMock(return_value=None),
        ),
    ):
        grade = await projects_service.apply_deterministic_quiz_answer(
            session,
            user_id=user_id,
            chat_id=uuid.uuid4(),
            project_id=project_id,
            assistant_content=VOCAB_FENCE,
            user_answer="B",
            attempt=1,  # try 1 of 3 — not exhausted
        )

    assert grade is not None
    assert grade.is_correct is False
    assert grade.tries_exhausted is False
    # SM-2 scheduling should NOT run (not exhausted)
    apply_mock.assert_not_awaited()
    # But the attempt should be recorded (increment + last_incorrect_at + miss event)
    record_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_new_vocab_quiz_word_lands_in_current_path_chapter():
    from app.models.orm import Project

    session = AsyncMock()
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    project = Project(
        id=project_id,
        user_id=user_id,
        title="Español",
        kind="language",
        level="level1",
        target_language="es",
        learning_path=["Greetings", "Food"],
    )
    created = AsyncMock()

    with (
        patch(
            "app.repositories.projects.get_by_id",
            new=AsyncMock(return_value=project),
        ),
        patch(
            "app.repositories.project_items.find_quiz_candidates",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.repositories.project_items.list_for_user",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.projects.quiz_grading.create_item",
            new=AsyncMock(return_value=created),
        ) as create_mock,
        patch(
            "app.services.projects.quiz_grading.apply_quiz_result",
            new=AsyncMock(return_value=created),
        ),
        patch(
            "app.services.vocab_quiz.verified_correct_letter",
            new=AsyncMock(return_value="A"),
        ),
    ):
        grade = await projects_service.apply_deterministic_quiz_answer(
            session,
            user_id=user_id,
            chat_id=uuid.uuid4(),
            project_id=project_id,
            assistant_content=VOCAB_FENCE,
            user_answer="A",
            attempt=1,
        )

    assert grade is not None
    assert grade.is_correct is True
    assert create_mock.await_args.kwargs["list_title"] == "Greetings"
