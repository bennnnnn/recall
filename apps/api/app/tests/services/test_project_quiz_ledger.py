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
            "app.services.projects.projects_repo.get_by_id",
            new=AsyncMock(return_value=project),
        ),
        patch(
            "app.services.projects.project_items_repo.find_quiz_candidates",
            new=AsyncMock(return_value=[existing]),
        ),
        patch(
            "app.services.projects.quiz_grading.apply_quiz_result",
            new=AsyncMock(return_value=existing),
        ) as apply_mock,
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
