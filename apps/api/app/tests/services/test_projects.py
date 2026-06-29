from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.schemas import ProjectActionItem
from app.services import projects as projects_service


def _project(title: str, kind: str = "language"):
    p = MagicMock()
    p.id = uuid4()
    p.title = title
    p.kind = kind
    p.description = "Learn daily"
    p.level = "level1"
    return p


def _item(
    content: str,
    project_id,
    list_title: str = "Travel",
    mastered: bool = False,
    part_of_speech: str = "noun",
):
    item = MagicMock()
    item.id = uuid4()
    item.project_id = project_id
    item.list_title = list_title
    item.content = content
    item.note = None
    item.definition = f"definition of {content}"
    item.example_sentence = None
    item.part_of_speech = part_of_speech
    item.status = "mastered" if mastered else "new"
    item.mastered = mastered
    item.created_at = datetime.now(UTC)
    item.last_reviewed_at = None
    return item


def test_format_projects_block_groups_lists():
    project = _project("Learning English")
    item_a = _item("hello", project.id)
    item_b = _item("goodbye", project.id, mastered=True)
    block = projects_service.format_projects_block([project], [item_a, item_b])
    assert "### Learning English (language, level1)" in block
    assert "1/2 mastered" in block
    assert "#### Nouns" in block
    assert "○ hello" in block
    assert "✓ goodbye" in block


@pytest.mark.asyncio
async def test_apply_project_actions_create_and_add():
    session = AsyncMock()
    user_id = uuid4()
    project = _project("Spanish")
    with (
        patch.object(
            projects_service.projects_repo,
            "list_for_user",
            AsyncMock(side_effect=[[], [project]]),
        ),
        patch.object(
            projects_service.projects_repo,
            "create",
            AsyncMock(return_value=project),
        ) as create_mock,
        patch.object(
            projects_service.project_items_repo,
            "list_for_user",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            projects_service.project_items_repo,
            "create",
            AsyncMock(return_value=_item("hola", project.id)),
        ) as add_mock,
    ):
        applied = await projects_service.apply_project_actions(
            session,
            user_id=user_id,
            actions=[
                ProjectActionItem(
                    action="create_project",
                    project_title="Spanish",
                    kind="vocabulary",
                    description="Daily words",
                    content="hola",
                    list_title="Basics",
                ),
            ],
        )
    assert applied == 2
    create_mock.assert_awaited_once()
    add_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_apply_project_actions_master():
    session = AsyncMock()
    user_id = uuid4()
    project = _project("English")
    existing = _item("apple", project.id)
    with (
        patch.object(
            projects_service.projects_repo,
            "list_for_user",
            AsyncMock(return_value=[project]),
        ),
        patch.object(
            projects_service.project_items_repo,
            "list_for_user",
            AsyncMock(return_value=[existing]),
        ),
        patch.object(
            projects_service.project_items_repo,
            "update",
            AsyncMock(return_value=existing),
        ) as update_mock,
    ):
        applied = await projects_service.apply_project_actions(
            session,
            user_id=user_id,
            actions=[
                ProjectActionItem(
                    action="master",
                    project_title="English",
                    list_title="Travel",
                    content="apple",
                ),
            ],
        )
    assert applied == 1
    update_mock.assert_awaited()


@pytest.mark.asyncio
async def test_apply_project_actions_delete_project():
    session = AsyncMock()
    user_id = uuid4()
    project = _project("Old project")
    with (
        patch.object(
            projects_service.projects_repo,
            "list_for_user",
            AsyncMock(return_value=[project]),
        ),
        patch.object(
            projects_service.project_items_repo,
            "list_for_user",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            projects_service.projects_repo,
            "delete_by_id",
            AsyncMock(return_value=True),
        ) as delete_mock,
    ):
        applied = await projects_service.apply_project_actions(
            session,
            user_id=user_id,
            actions=[
                ProjectActionItem(action="delete_project", project_title="Old project"),
            ],
        )
    assert applied == 1
    delete_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_load_projects_for_prompt():
    session = AsyncMock()
    project = _project("English")
    with (
        patch.object(
            projects_service.projects_repo,
            "list_for_user",
            AsyncMock(return_value=[project]),
        ),
        patch.object(
            projects_service.project_items_repo,
            "list_for_user",
            AsyncMock(return_value=[_item("run", project.id)]),
        ),
    ):
        block = await projects_service.load_projects_for_prompt(session, uuid4(), Settings())
    assert "English" in block
    assert "run" in block


@pytest.mark.asyncio
async def test_sync_projects_from_transcript_adds_words():
    from app.gateways import mock_llm
    from app.services.projects import sync_projects_from_transcript

    session = AsyncMock()
    user_id = uuid4()
    chat_id = uuid4()
    project = _project("Learning English")
    settings = Settings(mock_llm_enabled=True)
    settings.openrouter_api_key = ""

    transcript = (
        "User: Add hello, hola, and gracias to my Learning English travel list\n"
        "Assistant: I've added hello, hola, and gracias to your Travel list."
    )

    with (
        patch.object(
            projects_service.projects_repo,
            "list_for_user",
            AsyncMock(return_value=[project]),
        ),
        patch.object(
            projects_service.project_items_repo,
            "list_for_user",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            projects_service.project_items_repo,
            "create",
            AsyncMock(side_effect=lambda *a, **kw: _item(kw["content"], project.id)),
        ) as create_mock,
        patch.object(mock_llm, "should_mock_llm", return_value=True),
    ):
        result = await sync_projects_from_transcript(
            session,
            settings,
            user_id=user_id,
            chat_id=chat_id,
            transcript=transcript,
        )

    assert result is not None
    assert len(result.actions) >= 3
    assert create_mock.await_count >= 3


@pytest.mark.asyncio
async def test_mock_extract_vocab_terms():
    from app.gateways.mock_llm import _extract_vocab_terms

    terms = _extract_vocab_terms(
        "User: add hello, hola, and gracias\n"
        "Assistant: Added 'hello', 'hola', and 'gracias' to Travel."
    )
    assert "hello" in terms
    assert "hola" in terms
    assert "gracias" in terms


@pytest.mark.asyncio
async def test_load_project_for_prompt_scoped():
    session = AsyncMock()
    user_id = uuid4()
    project_id = uuid4()
    project = _project("Spanish")
    project.id = project_id
    item = _item("hola", project_id)

    with (
        patch.object(
            projects_service.projects_repo,
            "get_by_id",
            AsyncMock(return_value=project),
        ),
        patch.object(
            projects_service.project_items_repo,
            "list_for_user",
            AsyncMock(return_value=[item]),
        ),
    ):
        block = await projects_service.load_project_for_prompt(
            session, user_id, project_id, Settings()
        )

    assert "linked to ONE learning topic" in block
    assert "Spanish" in block
    assert "hola" in block
