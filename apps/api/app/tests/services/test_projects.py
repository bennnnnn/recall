from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.schemas import ProjectActionItem
from app.services import projects as projects_service


class _FakeSessionCM:
    def __init__(self, session: AsyncMock):
        self._session = session

    async def __aenter__(self) -> AsyncMock:
        return self._session

    async def __aexit__(self, *args: object) -> None:
        return None


def _session_local_side_effect(session: AsyncMock):
    return [_FakeSessionCM(session), _FakeSessionCM(session)]


def test_transcript_implies_project_sync():
    pid = uuid4()
    assert projects_service.transcript_implies_project_sync(
        "User: hello\nAssistant: Hi!",
        chat_project_id=pid,
    )
    assert projects_service.transcript_implies_project_sync(
        "User: add apple\nAssistant: Added apple to your vocabulary list."
    )
    assert not projects_service.transcript_implies_project_sync("User: hello\nAssistant: Hi there!")


def _project(title: str, kind: str = "language"):
    p = MagicMock()
    p.id = uuid4()
    p.title = title
    p.kind = kind
    p.description = "Learn daily"
    p.level = "level1"
    p.target_language = "en"
    return p


def _item(
    content: str,
    project_id,
    list_title: str = "Travel",
    mastered: bool = False,
):
    item = MagicMock()
    item.id = uuid4()
    item.project_id = project_id
    item.list_title = list_title
    item.content = content
    item.note = None
    item.definition = f"definition of {content}"
    item.example_sentence = None
    item.status = "mastered" if mastered else "new"
    item.mastered = mastered
    item.created_at = datetime.now(UTC)
    item.last_reviewed_at = None
    item.mastered_at = None
    item.last_incorrect_at = None
    item.review_count = 0
    item.pronunciation_url = None
    return item


def _patch_count_stats_by_project(stats: dict):
    async def _mock(_session, project_ids, *, timezone_by_project=None):
        return {pid: stats for pid in project_ids}

    return patch.object(
        projects_service.project_items_repo,
        "count_stats_by_project",
        AsyncMock(side_effect=_mock),
    )


def test_format_projects_block_groups_lists():
    project = _project("Learning English")
    item_a = _item("hello", project.id)
    item_b = _item("goodbye", project.id, mastered=True)
    block = projects_service.format_projects_block([project], [item_a, item_b])
    assert "### Learning English (language, level1)" in block
    assert "1/2 mastered" in block
    assert "#### Travel" in block
    assert "○ hello" in block
    assert "✓ goodbye" in block


@pytest.mark.asyncio
async def test_apply_project_actions_skips_duplicate_language_project():
    session = AsyncMock()
    user_id = uuid4()
    existing = _project("English")
    with (
        patch.object(
            projects_service.projects_repo,
            "list_for_user",
            AsyncMock(return_value=[existing]),
        ),
        patch.object(
            projects_service.project_items_repo,
            "list_for_user",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            projects_service.projects_repo,
            "create",
            AsyncMock(),
        ) as create_mock,
    ):
        applied = await projects_service.apply_project_actions(
            session,
            user_id=user_id,
            actions=[
                ProjectActionItem(
                    action="create_project",
                    project_title="English · Elementary",
                    kind="language",
                    description="More words",
                ),
            ],
        )
    assert applied == 0
    create_mock.assert_not_awaited()


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
async def test_apply_project_actions_invalidates_home_cache():
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
        ),
        patch.object(
            projects_service.project_items_repo,
            "list_for_user",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            projects_service,
            "_invalidate_home_for_user",
            AsyncMock(),
        ) as invalidate_mock,
    ):
        applied = await projects_service.apply_project_actions(
            session,
            user_id=user_id,
            actions=[
                ProjectActionItem(
                    action="create_project",
                    project_title="Spanish",
                    kind="vocabulary",
                ),
            ],
        )
    assert applied == 1
    invalidate_mock.assert_awaited_once_with(user_id)


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
    settings = Settings(mock_llm_enabled=True, openrouter_api_key="")
    settings.openrouter_api_key = ""

    transcript = (
        "User: Add hello, hola, and gracias to my Learning English travel list\n"
        "Assistant: I've added hello, hola, and gracias to your Travel list."
    )

    with (
        patch(
            "app.core.db.SessionLocal",
            side_effect=_session_local_side_effect(session),
        ),
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
async def test_load_daily_learning_summary_for_prompt():
    session = AsyncMock()
    user = MagicMock()
    user.id = uuid4()
    user.timezone = "America/Los_Angeles"
    project = _project("English · Beginner")
    project.daily_goal = 5

    with (
        patch.object(
            projects_service.projects_repo,
            "list_for_user",
            AsyncMock(return_value=[project]),
        ),
        _patch_count_stats_by_project(
            {
                "total": 20,
                "mastered_today": 2,
                "pending_today": 0,
            }
        ),
    ):
        block = await projects_service.load_daily_learning_summary_for_prompt(
            session, user, Settings()
        )

    assert "Today's learning progress" in block
    assert "English · Beginner" in block
    assert "vocabulary quiz" in block
    assert "2/5 done" in block
    assert "3 left for today's vocabulary quiz" in block


@pytest.mark.asyncio
async def test_load_daily_learning_summary_not_started_today():
    session = AsyncMock()
    user = MagicMock()
    user.id = uuid4()
    user.timezone = "America/Los_Angeles"
    project = _project("English · Beginner")
    project.daily_goal = 5

    with (
        patch.object(
            projects_service.projects_repo,
            "list_for_user",
            AsyncMock(return_value=[project]),
        ),
        _patch_count_stats_by_project(
            {
                "total": 12,
                "mastered_today": 0,
                "pending_today": 0,
            }
        ),
    ):
        block = await projects_service.load_daily_learning_summary_for_prompt(
            session, user, Settings(), client_timezone="America/Los_Angeles"
        )

    assert "0/5 done" in block
    assert "not started" in block
    assert "vocabulary quiz" in block


@pytest.mark.asyncio
async def test_load_daily_learning_summary_skips_completed_goal():
    session = AsyncMock()
    user = MagicMock()
    user.id = uuid4()
    user.timezone = "America/Los_Angeles"
    project = _project("English · Beginner")
    project.daily_goal = 5

    with (
        patch.object(
            projects_service.projects_repo,
            "list_for_user",
            AsyncMock(return_value=[project]),
        ),
        _patch_count_stats_by_project(
            {
                "total": 20,
                "mastered_today": 5,
                "pending_today": 0,
            }
        ),
    ):
        block = await projects_service.load_daily_learning_summary_for_prompt(
            session, user, Settings()
        )

    assert block == ""


@pytest.mark.asyncio
async def test_load_daily_learning_summary_trivia_label():
    session = AsyncMock()
    user = MagicMock()
    user.id = uuid4()
    user.timezone = "America/Los_Angeles"
    project = _project("World History")
    project.kind = "trivia"
    project.daily_goal = 5

    with (
        patch.object(
            projects_service.projects_repo,
            "list_for_user",
            AsyncMock(return_value=[project]),
        ),
        _patch_count_stats_by_project(
            {
                "total": 8,
                "mastered_today": 8,
                "pending_today": 0,
            }
        ),
    ):
        block = await projects_service.load_daily_learning_summary_for_prompt(
            session, user, Settings()
        )

    assert block == ""


@pytest.mark.asyncio
async def test_load_daily_learning_summary_trivia_incomplete():
    session = AsyncMock()
    user = MagicMock()
    user.id = uuid4()
    user.timezone = "America/Los_Angeles"
    project = _project("World History")
    project.kind = "trivia"
    project.daily_goal = 5

    with (
        patch.object(
            projects_service.projects_repo,
            "list_for_user",
            AsyncMock(return_value=[project]),
        ),
        _patch_count_stats_by_project(
            {
                "total": 8,
                "mastered_today": 3,
                "pending_today": 0,
            }
        ),
    ):
        block = await projects_service.load_daily_learning_summary_for_prompt(
            session, user, Settings()
        )

    assert "general knowledge quiz" in block
    assert "3/5 done" in block
    assert "3 correct" in block


@pytest.mark.asyncio
async def test_load_daily_learning_summary_batches_stats():
    session = AsyncMock()
    user = MagicMock()
    user.id = uuid4()
    user.timezone = "UTC"
    english = _project("English · Beginner")
    english.daily_goal = 5
    trivia = _project("World History", kind="trivia")
    trivia.daily_goal = 5
    general = _project("Research notes", kind="research")

    async def _mock(_session, project_ids, *, timezone_by_project=None):
        by_id = {
            english.id: {"total": 10, "mastered_today": 2, "pending_today": 0},
            trivia.id: {"total": 8, "mastered_today": 1, "pending_today": 0},
        }
        return {pid: by_id[pid] for pid in project_ids if pid in by_id}

    with (
        patch.object(
            projects_service.projects_repo,
            "list_for_user",
            AsyncMock(return_value=[english, trivia, general]),
        ),
        patch.object(
            projects_service.project_items_repo,
            "count_stats_by_project",
            AsyncMock(side_effect=_mock),
        ) as stats_mock,
    ):
        block = await projects_service.load_daily_learning_summary_for_prompt(
            session, user, Settings()
        )

    stats_mock.assert_awaited_once()
    assert set(stats_mock.await_args.args[1]) == {english.id, trivia.id}
    assert "English · Beginner" in block
    assert "World History" in block


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
        patch.object(
            projects_service.project_items_repo,
            "list_quiz_exclusion_contents",
            AsyncMock(return_value=[]),
        ),
    ):
        block = await projects_service.load_project_for_prompt(
            session, user_id, project_id, Settings()
        )

    assert "linked to ONE learning topic" in block
    assert "Spanish" in block
    assert "hola" in block


@pytest.mark.asyncio
async def test_load_project_for_prompt_chat_mode():
    session = AsyncMock()
    user_id = uuid4()
    project_id = uuid4()
    project = _project("English")
    project.id = project_id

    with (
        patch.object(
            projects_service.projects_repo,
            "get_by_id",
            AsyncMock(return_value=project),
        ),
        patch.object(
            projects_service.project_items_repo,
            "list_for_user",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            projects_service.project_items_repo,
            "list_quiz_exclusion_contents",
            AsyncMock(return_value=[]),
        ),
    ):
        block = await projects_service.load_project_for_prompt(
            session, user_id, project_id, Settings(), quiz_mode="chat"
        )

    assert "daily vocabulary in chat" in block
    assert "learning formats" in block.lower() or "teach→use" in block
    assert "vocab_card" in block
    assert "Presentation mode: chat" in block
    assert "multiple choice only" not in block.lower()


@pytest.mark.asyncio
async def test_load_project_for_prompt_trivia_chat_mode():
    session = AsyncMock()
    user_id = uuid4()
    project_id = uuid4()
    project = _project("General knowledge", kind="trivia")
    project.id = project_id

    with (
        patch.object(
            projects_service.projects_repo,
            "get_by_id",
            AsyncMock(return_value=project),
        ),
        patch.object(
            projects_service.project_items_repo,
            "list_for_user",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            projects_service.project_items_repo,
            "list_quiz_exclusion_contents",
            AsyncMock(return_value=[]),
        ),
    ):
        block = await projects_service.load_project_for_prompt(
            session, user_id, project_id, Settings(), quiz_mode="chat"
        )

    assert "daily general knowledge in chat" in block
    assert "vocab_quiz" in block
    assert "Do NOT use vocab_card" in block
    assert "Bonus quiz" in block


@pytest.mark.asyncio
async def test_load_project_for_prompt_uses_chat_mode_even_when_exam_requested():
    session = AsyncMock()
    user_id = uuid4()
    project_id = uuid4()
    project = _project("English")
    project.id = project_id

    with (
        patch.object(
            projects_service.projects_repo,
            "get_by_id",
            AsyncMock(return_value=project),
        ),
        patch.object(
            projects_service.project_items_repo,
            "list_for_user",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            projects_service.project_items_repo,
            "list_quiz_exclusion_contents",
            AsyncMock(return_value=[]),
        ),
    ):
        block = await projects_service.load_project_for_prompt(
            session, user_id, project_id, Settings(), quiz_mode="exam"
        )

    assert "presentation mode: chat" in block.lower()
    assert "daily vocabulary in chat" in block.lower()
    assert "exam (legacy)" not in block.lower()


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
    assert "teach→use" in prompt or "vocab_card" in prompt
    assert "failed recently" in prompt.lower()
    assert "Daily Quiz panel" not in prompt


def test_looks_like_vocab_question():
    teach = "**Ephemeral**\nlasting for a very short time.\nWhat does **ephemeral** mean?"
    assert projects_service.looks_like_vocab_question(teach) is True
    assert projects_service.looks_like_vocab_question("Hello! How can I help?") is False
    card = '```vocab_card\n{"word":"hope","definition":"wanting something"}\n```\nWrite a sentence.'
    assert projects_service.looks_like_vocab_question(card) is True
    sentence = "Write your own sentence with **serendipity**."
    assert projects_service.looks_like_vocab_question(sentence) is True


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
        patch.object(
            projects_service.project_items_repo,
            "list_quiz_exclusion_contents",
            AsyncMock(return_value=[]),
        ),
    ):
        block = await projects_service.load_project_quiz_context(
            session, user_id, project_id, Settings()
        )

    assert "Active vocabulary session" in block
    assert "apple" in block
    assert "vocab_quiz" in block or "teach→use" in block
    assert "NEXT word" in block


@pytest.mark.asyncio
async def test_load_project_quiz_context_retries_same_word_on_wrong():
    from app.services.vocab_quiz import QuizAnswerGrade

    session = AsyncMock()
    user_id = uuid4()
    project_id = uuid4()
    project = _project("English")
    project.id = project_id
    item = _item("ephemeral", project_id)

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
        patch.object(
            projects_service.project_items_repo,
            "list_quiz_exclusion_contents",
            AsyncMock(return_value=[]),
        ),
    ):
        block = await projects_service.load_project_quiz_context(
            session,
            user_id,
            project_id,
            Settings(),
            quiz_grade=QuizAnswerGrade(
                is_correct=False,
                user_letter="A",
                correct_letter="B",
                word="ephemeral",
            ),
        )

    assert "WRONG" in block
    assert "ephemeral" in block
    assert "Do NOT redisplay" in block
    assert "NEXT word" not in block
    assert "SAME word" not in block


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


def test_format_projects_block_trivia_topics():
    project = _project("World facts", kind="trivia")
    project.description = "history,science"
    item = _item("Colossus of Rhodes", project.id, list_title="History")
    block = projects_service.format_projects_block([project], [item])
    assert "topics=history,science" in block
    assert "#### History" in block


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
async def test_apply_project_actions_skips_master_after_recent_miss():
    from datetime import UTC, datetime

    session = AsyncMock()
    user_id = uuid4()
    project = _project("English")
    existing = _item("luminous", project.id)
    existing.status = "learning"
    existing.last_incorrect_at = datetime.now(UTC)

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
                    project_title=project.title,
                    list_title="General",
                    content="luminous",
                )
            ],
        )

    assert applied == 0
    update_mock.assert_not_awaited()


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
async def test_apply_project_actions_start_learning_records_failed_quiz():
    session = AsyncMock()
    user_id = uuid4()
    project = _project("English")
    existing = _item("serendipity", project.id)
    existing.status = "new"
    existing.last_incorrect_at = None

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
            "apply_quiz_result",
            AsyncMock(return_value=existing),
        ) as apply_result,
    ):
        applied = await projects_service.apply_project_actions(
            session,
            user_id=user_id,
            actions=[
                ProjectActionItem(
                    action="start_learning",
                    project_title="English",
                    content="serendipity",
                ),
            ],
        )

    assert applied == 1
    apply_result.assert_awaited_once()
    assert apply_result.await_args.kwargs["is_correct"] is False


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
async def test_apply_project_actions_delete_does_not_fuzzy_match_substring():
    """BUG FIX regression: deck has "category" but not "cat" — a delete for
    "cat" must no-op, not fall back to substring-matching "category"."""
    session = AsyncMock()
    user_id = uuid4()
    project = _project("English")
    existing = _item("category", project.id)
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
            "delete_by_id",
            AsyncMock(),
        ) as delete_mock,
    ):
        applied = await projects_service.apply_project_actions(
            session,
            user_id=user_id,
            actions=[
                ProjectActionItem(
                    action="delete",
                    project_title="English",
                    list_title="Travel",
                    content="cat",
                ),
            ],
        )
    assert applied == 0
    delete_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_project_actions_master_does_not_fuzzy_match_substring():
    """Same false-positive-match bug for `master` — "cat" must not resolve
    to an existing "category" item."""
    session = AsyncMock()
    user_id = uuid4()
    project = _project("English")
    existing = _item("category", project.id)
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
            AsyncMock(),
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
                    content="cat",
                ),
            ],
        )
    assert applied == 0
    update_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_project_actions_add_not_skipped_as_fuzzy_duplicate():
    """BUG FIX regression: deck has "category" but not "cat" — adding "cat"
    must NOT be silently skipped as a "duplicate" of "category"."""
    session = AsyncMock()
    user_id = uuid4()
    project = _project("English")
    existing = _item("category", project.id, list_title="nouns")
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
            AsyncMock(return_value=_item("cat", project.id, list_title="nouns")),
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
                    content="cat",
                ),
            ],
        )
    assert applied == 1
    create_mock.assert_awaited_once()


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
        patch(
            "app.core.db.SessionLocal",
            side_effect=_session_local_side_effect(session),
        ),
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
            settings,
            user_id=user_id,
            chat_id=chat_id,
            transcript="add world",
        )

    assert result is extraction
    apply_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_sync_projects_from_transcript_releases_db_before_llm():
    session = AsyncMock()
    session.commit = AsyncMock()
    db_open_during_extract: list[bool] = []

    class _TrackingSessionCM(_FakeSessionCM):
        def __init__(self) -> None:
            super().__init__(session)
            self.open = False

        async def __aenter__(self) -> AsyncMock:
            self.open = True
            return await super().__aenter__()

        async def __aexit__(self, *args: object) -> None:
            self.open = False
            await super().__aexit__(*args)

    load_cm = _TrackingSessionCM()
    apply_cm = _TrackingSessionCM()

    async def fake_extract(*_args: object, **_kwargs: object) -> None:
        db_open_during_extract.append(load_cm.open or apply_cm.open)
        return None

    with (
        patch("app.core.db.SessionLocal", side_effect=[load_cm, apply_cm]),
        patch.object(projects_service.projects_repo, "list_for_user", AsyncMock(return_value=[])),
        patch.object(
            projects_service.project_items_repo,
            "list_for_user",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.gateways.litellm_gateway.extract_project_actions",
            AsyncMock(side_effect=fake_extract),
        ),
    ):
        await projects_service.sync_projects_from_transcript(
            Settings(),
            user_id=uuid4(),
            chat_id=uuid4(),
            transcript="add word",
        )

    assert db_open_during_extract == [False]
    assert session.commit.await_count == 2


@pytest.mark.asyncio
async def test_sync_projects_from_transcript_returns_none_on_error():
    session = AsyncMock()
    settings = Settings()

    with (
        patch(
            "app.core.db.SessionLocal",
            side_effect=_session_local_side_effect(session),
        ),
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
        patch.object(
            projects_service.project_items_repo,
            "list_quiz_exclusion_contents",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.gateways.litellm_gateway.extract_project_actions",
            AsyncMock(side_effect=RuntimeError("boom")),
        ),
    ):
        result = await projects_service.sync_projects_from_transcript(
            settings,
            user_id=uuid4(),
            chat_id=uuid4(),
            transcript="add word",
        )

    assert result is None


@pytest.mark.asyncio
async def test_load_project_for_prompt_trivia_hint():
    session = AsyncMock()
    user_id = uuid4()
    project_id = uuid4()
    project = _project("World", kind="trivia")
    project.id = project_id
    project.description = "history"
    item = _item("Colossus of Rhodes", project_id, list_title="History")

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
        patch.object(
            projects_service.project_items_repo,
            "list_quiz_exclusion_contents",
            AsyncMock(return_value=["Colossus of Rhodes"]),
        ),
        patch.object(
            projects_service.project_items_repo,
            "count_stats",
            AsyncMock(
                return_value={
                    "total": 1,
                    "mastered_count": 0,
                    "new_count": 1,
                    "learning_count": 0,
                    "mastered_today": 0,
                    "missed_today": 0,
                    "pending_today": 1,
                }
            ),
        ),
        patch(
            "app.repositories.users.get_by_id",
            AsyncMock(return_value=MagicMock(timezone="UTC")),
        ),
    ):
        block = await projects_service.load_project_for_prompt(
            session, user_id, project_id, Settings()
        )

    assert "trivia" in block.lower() or "general knowledge" in block.lower()
    assert "Colossus of Rhodes" in block
    assert "Do NOT ask these again" in block
    assert "quiz ledger" in block


def test_chat_tutor_hints_acknowledge_completed_daily_goal():
    """When the daily goal is already met, the chat tutor prompts must tell the
    model to acknowledge completion and ask about bonus/raising the goal — not
    silently serve a new question on a vague 'let's continue'."""
    from app.services.projects import (
        DAILY_GOAL_COMPLETE_BEHAVIOR,
        LANGUAGE_CHAT_TUTOR_HINT,
        TRIVIA_CHAT_TUTOR_HINT,
    )

    assert DAILY_GOAL_COMPLETE_BEHAVIOR in LANGUAGE_CHAT_TUTOR_HINT
    assert DAILY_GOAL_COMPLETE_BEHAVIOR in TRIVIA_CHAT_TUTOR_HINT
    # The behaviour must explicitly handle the "let's continue" case.
    assert "let's continue" in DAILY_GOAL_COMPLETE_BEHAVIOR.lower()
    assert "raise their daily goal" in DAILY_GOAL_COMPLETE_BEHAVIOR.lower()
