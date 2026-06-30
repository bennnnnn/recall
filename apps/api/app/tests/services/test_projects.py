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
    item.mastered_at = None
    item.review_count = 0
    item.pronunciation_url = None
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


def test_build_language_quiz_prompt_includes_vocab_quiz_fence():
    project = _project("English")
    stats = MagicMock()
    stats.total = 5
    stats.mastered_count = 1
    stats.new_count = 2
    stats.learning_count = 2
    stats.due_for_review = 1

    prompt = projects_service.build_language_quiz_prompt(project, stats)
    assert "vocab_quiz" in prompt
    assert '"correct"' in prompt
    assert "Begin with the first question now" in prompt


@pytest.mark.asyncio
async def test_load_project_quiz_context():
    session = AsyncMock()
    user_id = uuid4()
    project_id = uuid4()
    project = _project("English")
    project.id = project_id
    item = _item("apple", project_id)

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
        block = await projects_service.load_project_quiz_context(
            session, user_id, project_id, Settings()
        )

    assert "Active vocabulary quiz" in block
    assert "apple" in block
    assert "vocab_quiz" in block


@pytest.mark.asyncio
async def test_mock_project_actions_masters_on_quiz_answer():
    from app.gateways import mock_llm

    transcript = (
        "User: Start vocabulary quiz\n"
        "Assistant: **Word:** apple [noun]\nA) fruit\nB) car\nC) sky\nD) book\n"
        "User: B\n"
        "Assistant: Nice work — B is correct!"
    )
    snapshot = {
        "projects": [{"title": "English", "kind": "language", "items": [{"content": "apple"}]}]
    }
    result = await mock_llm.mock_project_actions(transcript, snapshot)
    assert result is not None
    assert any(a.action == "master" and a.content == "apple" for a in result.actions)


def test_group_items_and_build_stats():
    project_id = uuid4()
    items = [
        _item("alpha", project_id, list_title="Basics"),
        _item("beta", project_id, list_title="Basics", mastered=True),
    ]
    groups = projects_service.group_items(items)
    assert len(groups) == 1
    assert groups[0].list_title == "Basics"
    assert len(groups[0].items) == 2

    stats = projects_service.build_stats(items)
    assert stats.total == 2
    assert stats.mastered_count == 1
    assert stats.new_count == 1


def test_group_by_part_of_speech_orders_known_pos_first():
    project_id = uuid4()
    verb = _item("run", project_id, part_of_speech="verb")
    noun = _item("book", project_id, part_of_speech="noun")
    groups = projects_service.group_by_part_of_speech([verb, noun])
    assert groups[0].part_of_speech == "noun"
    assert groups[1].part_of_speech == "verb"


def test_group_programming_items_sorts_by_curriculum():
    project_id = uuid4()
    variables = _item("x", project_id, list_title="Variables")
    functions = _item("def foo", project_id, list_title="Functions")
    groups = projects_service.group_programming_items([functions, variables])
    assert groups[0].list_title == "Variables"
    assert groups[1].list_title == "Functions"


def test_format_projects_block_programming_stack():
    project = _project("Python basics", kind="programming")
    project.target_language = "python"
    item = _item("variable", project.id, list_title="Variables")
    block = projects_service.format_projects_block([project], [item])
    assert "stack=python" in block
    assert "Programming language: python" in block
    assert "#### Variables" in block


def test_format_projects_block_empty_items():
    project = _project("Empty")
    block = projects_service.format_projects_block([project], [])
    assert "(no words yet)" in block


def test_build_language_quiz_prompt_empty_progress():
    project = _project("English")
    stats = projects_service.build_stats([])
    prompt = projects_service.build_language_quiz_prompt(project, stats)
    assert "no words yet" in prompt.lower()


@pytest.mark.asyncio
async def test_apply_project_actions_start_learning_and_unmaster():
    session = AsyncMock()
    user_id = uuid4()
    project = _project("English")
    existing = _item("apple", project.id, mastered=True)
    existing.status = "mastered"

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
                    action="unmaster",
                    project_title="English",
                    list_title="nouns",
                    content="apple",
                ),
            ],
        )
    assert applied == 1
    update_mock.assert_awaited()


@pytest.mark.asyncio
async def test_apply_project_actions_delete_list():
    session = AsyncMock()
    user_id = uuid4()
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
            AsyncMock(return_value=[]),
        ),
        patch.object(
            projects_service.project_items_repo,
            "delete_by_list",
            AsyncMock(return_value=2),
        ) as delete_mock,
    ):
        applied = await projects_service.apply_project_actions(
            session,
            user_id=user_id,
            actions=[
                ProjectActionItem(
                    action="delete_list",
                    project_title="English",
                    list_title="Travel",
                ),
            ],
        )
    assert applied == 1
    delete_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_apply_project_actions_set_level_and_description():
    session = AsyncMock()
    user_id = uuid4()
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
            AsyncMock(return_value=[]),
        ),
        patch.object(
            projects_service.projects_repo,
            "update",
            AsyncMock(return_value=project),
        ) as update_mock,
    ):
        applied = await projects_service.apply_project_actions(
            session,
            user_id=user_id,
            actions=[
                ProjectActionItem(
                    action="set_description",
                    project_title="English",
                    description="Travel vocab",
                ),
                ProjectActionItem(
                    action="set_level",
                    project_title="English",
                    level="level3",
                ),
            ],
        )
    assert applied == 2
    assert update_mock.await_count == 2


@pytest.mark.asyncio
async def test_apply_project_actions_skips_duplicate_add():
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
            "create",
            AsyncMock(),
        ) as create_mock,
    ):
        applied = await projects_service.apply_project_actions(
            session,
            user_id=user_id,
            actions=[
                ProjectActionItem(
                    action="add",
                    project_title="English",
                    list_title="nouns",
                    content="apple",
                ),
            ],
        )
    assert applied == 0
    create_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_sync_projects_from_transcript_applies_litellm_actions():
    from app.models.schemas import ProjectExtractionResult

    session = AsyncMock()
    user_id = uuid4()
    chat_id = uuid4()
    project = _project("English")
    settings = Settings()

    extraction = ProjectExtractionResult(
        actions=[
            ProjectActionItem(
                action="add",
                project_title="English",
                list_title="nouns",
                content="world",
            )
        ]
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
        patch(
            "app.gateways.litellm_gateway.extract_project_actions",
            AsyncMock(return_value=extraction),
        ),
        patch.object(
            projects_service,
            "apply_project_actions",
            AsyncMock(return_value=1),
        ) as apply_mock,
    ):
        result = await projects_service.sync_projects_from_transcript(
            session,
            settings,
            user_id=user_id,
            chat_id=chat_id,
            transcript="add world",
        )

    assert result is extraction
    apply_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_sync_projects_from_transcript_returns_none_on_error():
    session = AsyncMock()
    settings = Settings()

    with (
        patch.object(
            projects_service.projects_repo,
            "list_for_user",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            projects_service.project_items_repo,
            "list_for_user",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.gateways.litellm_gateway.extract_project_actions",
            AsyncMock(side_effect=RuntimeError("boom")),
        ),
    ):
        result = await projects_service.sync_projects_from_transcript(
            session,
            settings,
            user_id=uuid4(),
            chat_id=uuid4(),
            transcript="add word",
        )

    assert result is None


@pytest.mark.asyncio
async def test_load_project_for_prompt_programming_hint():
    session = AsyncMock()
    user_id = uuid4()
    project_id = uuid4()
    project = _project("Python", kind="programming")
    project.id = project_id
    item = _item("variable", project_id, list_title="Variables")

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

    assert "programming" in block.lower()
    assert "Variables" in block
