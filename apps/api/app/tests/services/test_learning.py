from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.schemas import LearningActionItem
from app.repositories import learning as learning_repo
from app.repositories import learning_items as learning_items_repo
from app.services import learning as learning_service
from app.services.learning import prompt_context as learning_prompt_context
from app.services.learning import sync as learning_sync


@pytest.fixture(autouse=True)
def _utc_user_for_project_actions():
    user = MagicMock()
    user.timezone = "UTC"
    with (
        patch("app.repositories.users.get_by_id", AsyncMock(return_value=user)),
        patch("app.repositories.learning_practice.list_events", AsyncMock(return_value=[])),
        patch(
            "app.repositories.learning_items.list_miss_events_for_items", AsyncMock(return_value={})
        ),
    ):
        yield


class _FakeSessionCM:
    def __init__(self, session: AsyncMock):
        self._session = session

    async def __aenter__(self) -> AsyncMock:
        return self._session

    async def __aexit__(self, *args: object) -> None:
        return None


def _session_local_side_effect(session: AsyncMock):
    return [_FakeSessionCM(session), _FakeSessionCM(session)]


@asynccontextmanager
async def _nested_savepoint():
    yield


def _session_with_savepoint() -> AsyncMock:
    """AsyncMock session whose begin_nested() is sync, like SQLAlchemy's."""
    session = AsyncMock()
    session.begin_nested = MagicMock(side_effect=_nested_savepoint)
    return session


def test_transcript_implies_learning_sync():
    pid = uuid4()
    assert learning_service.transcript_implies_learning_sync(
        "User: hello\nAssistant: Hi!",
        chat_project_id=pid,
    )
    assert learning_service.transcript_implies_learning_sync(
        "User: add apple\nAssistant: Added apple to your vocabulary list."
    )
    assert not learning_service.transcript_implies_learning_sync(
        "User: hello\nAssistant: Hi there!"
    )
    assert learning_service.transcript_implies_learning_sync("User: cuales son mis proyectos")


def _project(title: str, kind: str = "language"):
    p = MagicMock()
    p.id = uuid4()
    p.title = title
    p.kind = kind
    p.description = "Learn daily"
    p.level = "level1"
    p.target_language = "en"
    p.created_at = datetime.now(UTC)
    p.daily_goal_history = None
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
    item.ipa = None
    item.vocabulary_kind = "word"
    item.verb_kind = None
    item.noun_kind = None
    item.due_at = None
    item.last_completed_at = None
    item.last_incorrect_at = None
    item.part_of_speech = None
    item.simple_gloss = None
    item.status = "mastered" if mastered else "new"
    item.mastered = mastered
    item.created_at = datetime.now(UTC)
    item.last_reviewed_at = None
    item.mastered_at = None
    item.last_incorrect_at = None
    item.review_count = 0
    item.pronunciation_url = None
    return item


def _catalog_item(project_id, *, language="en", chapter=0, index=0, mastered=False):
    from app.content.vocab_catalog import path_decks_for_language
    from app.services.learning.catalog_items import word_values

    deck = path_decks_for_language(language)[chapter]
    word = deck.words[index]
    item = _item(word.content, project_id, list_title=deck.title, mastered=mastered)
    for name, value in word_values(deck, word).items():
        setattr(item, name, value)
    return item


def _patch_count_stats_by_learning(stats: dict):
    async def _mock(_session, project_ids, *, timezone_by_project=None):
        return {pid: stats for pid in project_ids}

    return patch(
        "app.services.learning.stats.count_stats_by_learning",
        AsyncMock(side_effect=_mock),
    )


def test_format_learning_block_groups_lists():
    project = _project("Learning English")
    item_a = _item("hello", project.id)
    item_b = _item("goodbye", project.id, mastered=True)
    block = learning_service.format_learning_block([project], [item_a, item_b])
    assert f"### Learning English (id={project.id}, language)" in block
    assert "1/2 mastered" in block
    assert "#### Travel" in block
    assert "○ hello" in block
    assert "✓ goodbye" in block


@pytest.mark.asyncio
async def test_apply_learning_actions_skips_duplicate_language_project():
    session = AsyncMock()
    user_id = uuid4()
    existing = _project("English")
    with (
        patch.object(
            learning_repo,
            "list_for_user",
            AsyncMock(return_value=[existing]),
        ),
        patch.object(
            learning_items_repo,
            "list_recent_for_learning",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            learning_repo,
            "create",
            AsyncMock(),
        ) as create_mock,
    ):
        applied = await learning_service.apply_learning_actions(
            session,
            user_id=user_id,
            actions=[
                LearningActionItem(
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
async def test_apply_learning_actions_creates_second_target_language():
    session = _session_with_savepoint()
    user_id = uuid4()
    existing = _project("English")
    existing.target_language = "en"
    created = _project("Spanish")
    created.target_language = "es"
    with (
        patch.object(
            learning_repo,
            "list_for_user",
            AsyncMock(side_effect=[[existing], [existing, created]]),
        ),
        patch.object(
            learning_items_repo,
            "list_recent_for_learning",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            learning_repo,
            "create",
            AsyncMock(return_value=created),
        ) as create_mock,
    ):
        applied = await learning_service.apply_learning_actions(
            session,
            user_id=user_id,
            actions=[
                LearningActionItem(
                    action="create_project",
                    project_title="Spanish",
                    kind="language",
                    target_language="es",
                ),
            ],
        )
    assert applied == 1
    assert create_mock.await_args.kwargs["target_language"] == "es"


@pytest.mark.asyncio
async def test_create_learning_project_allows_second_language():
    session = AsyncMock()
    user = MagicMock()
    user.id = uuid4()
    user.locale = "en"
    user.timezone = "UTC"
    created = _project("Español · Beginner")
    created.target_language = "es"
    with (
        patch.object(learning_repo, "find_language_by_target", AsyncMock(return_value=None)),
        patch.object(learning_repo, "create", AsyncMock(return_value=created)) as create_mock,
        patch("app.services.home.invalidate_home_cache", AsyncMock()),
        patch("app.services.learning.crud.enqueue_language_path_job", AsyncMock()) as enqueue_path,
    ):
        result = await learning_service.create_learning_project(
            session,
            user,
            title="Español · Beginner",
            description=None,
            kind="language",
            target_language="es",
        )
    assert result is created
    assert create_mock.await_args.kwargs["target_language"] == "es"
    assert create_mock.await_args.kwargs["native_language"] == "en"
    enqueue_path.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_learning_project_rejects_unknown_target():
    session = AsyncMock()
    user = MagicMock()
    user.id = uuid4()
    user.locale = "en"
    with pytest.raises(ValueError, match="unsupported_target_language"):
        await learning_service.create_learning_project(
            session,
            user,
            title="Japanese",
            description=None,
            kind="language",
            target_language="ja",
        )


def test_normalize_and_infer_target_language():
    assert learning_service.normalize_target_language("ES") == "es"
    assert learning_service.normalize_target_language("ja") is None
    assert learning_service.language_display_name("fr") == "French"
    from app.services.learning.common import infer_target_language

    assert infer_target_language("Spanish vocabulary") == "es"
    assert infer_target_language("Words", "es") == "es"


@pytest.mark.asyncio
async def test_apply_learning_actions_handles_create_project_race():
    """Simulates two near-concurrent project-sync jobs both passing the
    in-memory "no existing language project" check before either commits —
    the DB partial unique index (migration 0055) rejects the second INSERT
    with IntegrityError. apply_learning_actions must roll back the SAVEPOINT
    and no-op rather than raising into the background job or discarding
    earlier uncommitted writes in the same batch."""
    from sqlalchemy.exc import IntegrityError

    session = _session_with_savepoint()
    user_id = uuid4()
    with (
        patch.object(
            learning_repo,
            "list_for_user",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            learning_items_repo,
            "list_recent_for_learning",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            learning_repo,
            "create",
            AsyncMock(side_effect=IntegrityError("insert", {}, Exception("dup key"))),
        ) as create_mock,
    ):
        applied = await learning_service.apply_learning_actions(
            session,
            user_id=user_id,
            actions=[
                LearningActionItem(
                    action="create_project",
                    project_title="English",
                    kind="language",
                ),
            ],
        )

    assert applied == 0
    create_mock.assert_awaited_once()
    session.rollback.assert_not_awaited()
    session.begin_nested.assert_called_once()


@pytest.mark.asyncio
async def test_apply_learning_actions_create_and_add():
    session = _session_with_savepoint()
    user_id = uuid4()
    project = _project("Spanish")
    with (
        patch.object(
            learning_repo,
            "list_for_user",
            AsyncMock(side_effect=[[], [project]]),
        ),
        patch.object(
            learning_repo,
            "create",
            AsyncMock(return_value=project),
        ) as create_mock,
        patch.object(
            learning_items_repo,
            "list_recent_for_learning",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            learning_items_repo,
            "get_by_list_content",
            AsyncMock(return_value=None),
        ),
        patch.object(
            learning_items_repo,
            "create",
            AsyncMock(return_value=_item("hola", project.id)),
        ) as add_mock,
    ):
        applied = await learning_service.apply_learning_actions(
            session,
            user_id=user_id,
            actions=[
                LearningActionItem(
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
    assert create_mock.await_args.kwargs["commit"] is False
    assert add_mock.await_args.kwargs["commit"] is False
    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_learning_actions_rolls_back_whole_batch_on_late_failure():
    session = AsyncMock()
    user_id = uuid4()
    project = _project("English")
    update = AsyncMock(side_effect=[project, RuntimeError("second write failed")])

    with (
        patch.object(learning_repo, "list_for_user", AsyncMock(return_value=[project])),
        patch.object(
            learning_items_repo,
            "list_recent_for_learning",
            AsyncMock(return_value=[]),
        ),
        patch.object(learning_repo, "update", update),
        patch(
            "app.services.learning.common._invalidate_home_for_user",
            AsyncMock(),
        ) as invalidate,
    ):
        with pytest.raises(RuntimeError, match="second write failed"):
            await learning_service.apply_learning_actions(
                session,
                user_id=user_id,
                actions=[
                    LearningActionItem(
                        action="set_description",
                        project_title="English",
                        description="First",
                    ),
                    LearningActionItem(
                        action="set_description",
                        project_title="English",
                        description="Second",
                    ),
                ],
            )

    assert update.await_count == 2
    assert all(call.kwargs["commit"] is False for call in update.await_args_list)
    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once()
    invalidate.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_learning_actions_invalidates_home_cache():
    session = _session_with_savepoint()
    user_id = uuid4()
    project = _project("Spanish")
    with (
        patch.object(
            learning_repo,
            "list_for_user",
            AsyncMock(side_effect=[[], [project]]),
        ),
        patch.object(
            learning_repo,
            "create",
            AsyncMock(return_value=project),
        ),
        patch.object(
            learning_items_repo,
            "list_recent_for_learning",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.learning.common._invalidate_home_for_user",
            AsyncMock(),
        ) as invalidate_mock,
    ):
        applied = await learning_service.apply_learning_actions(
            session,
            user_id=user_id,
            actions=[
                LearningActionItem(
                    action="create_project",
                    project_title="Spanish",
                    kind="vocabulary",
                ),
            ],
        )
    assert applied == 1
    invalidate_mock.assert_awaited_once_with(user_id)


@pytest.mark.asyncio
async def test_apply_learning_actions_master():
    session = AsyncMock()
    user_id = uuid4()
    project = _project("English")
    existing = _item("apple", project.id)
    with (
        patch.object(
            learning_repo,
            "list_for_user",
            AsyncMock(return_value=[project]),
        ),
        patch.object(
            learning_items_repo,
            "list_recent_for_learning",
            AsyncMock(return_value=[existing]),
        ),
        patch.object(
            learning_items_repo,
            "update",
            AsyncMock(return_value=existing),
        ) as update_mock,
    ):
        applied = await learning_service.apply_learning_actions(
            session,
            user_id=user_id,
            actions=[
                LearningActionItem(
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
async def test_apply_learning_actions_loads_items_scoped_per_project():
    """Dedup window must be per-project — a busy deck must not push another
    project's items out of the snapshot. The batched loader
    (list_recent_for_learning) is called once with every project id; the
    per-project row cap is the repo's responsibility (window function), so
    the dedup snapshot here must still contain the quiet deck's item alongside
    the busy deck's flood."""
    session = AsyncMock()
    user_id = uuid4()
    project_a = _project("Busy deck")
    project_b = _project("Quiet deck")
    list_recent = AsyncMock(
        return_value=[
            *[_item(f"flood-{i}", project_a.id) for i in range(3)],
            _item("keep-me", project_b.id),
        ]
    )
    with (
        patch.object(
            learning_repo,
            "list_for_user",
            AsyncMock(return_value=[project_a, project_b]),
        ),
        patch.object(learning_items_repo, "list_recent_for_learning", list_recent),
        patch.object(
            learning_items_repo,
            "count_for_project",
            AsyncMock(return_value=0),
        ),
        patch.object(
            learning_items_repo,
            "create",
            AsyncMock(return_value=_item("keep-me", project_b.id)),
        ) as create_mock,
    ):
        applied = await learning_service.apply_learning_actions(
            session,
            user_id=user_id,
            actions=[
                LearningActionItem(
                    action="add",
                    project_title="Quiet deck",
                    list_title="Travel",
                    content="keep-me",
                ),
            ],
        )

    assert applied == 0  # duplicate within project B's scoped window
    create_mock.assert_not_awaited()
    # One batched call carrying both project ids — not an N+1 loop.
    list_recent.assert_awaited_once()
    project_ids_arg = list_recent.await_args.args[2]
    assert project_a.id in project_ids_arg
    assert project_b.id in project_ids_arg


@pytest.mark.asyncio
async def test_apply_learning_actions_delete_project():
    """from_transcript=False simulates an explicit user-initiated caller
    (e.g. DELETE /projects/{id}) — destructive actions must still go through
    for that caller; only the default (transcript-extracted) path is blocked."""
    session = AsyncMock()
    user_id = uuid4()
    project = _project("Old project")
    with (
        patch.object(
            learning_repo,
            "list_for_user",
            AsyncMock(return_value=[project]),
        ),
        patch.object(
            learning_items_repo,
            "list_recent_for_learning",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            learning_repo,
            "delete_by_id",
            AsyncMock(return_value=True),
        ) as delete_mock,
    ):
        applied = await learning_service.apply_learning_actions(
            session,
            user_id=user_id,
            actions=[
                LearningActionItem(action="delete_project", project_title="Old project"),
            ],
            from_transcript=False,
        )
    assert applied == 1
    delete_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_apply_learning_actions_blocks_delete_project_by_default():
    """BUG FIX (was silent): the destructive-action guard used to live only
    in _apply_project_extraction_result — apply_learning_actions itself had
    no internal guard, so a future caller invoking it directly could bypass
    the block entirely. from_transcript now defaults to True (safe)."""
    session = AsyncMock()
    user_id = uuid4()
    project = _project("Old project")
    with (
        patch.object(
            learning_repo,
            "list_for_user",
            AsyncMock(return_value=[project]),
        ),
        patch.object(
            learning_items_repo,
            "list_recent_for_learning",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            learning_repo,
            "delete_by_id",
            AsyncMock(return_value=True),
        ) as delete_mock,
    ):
        applied = await learning_service.apply_learning_actions(
            session,
            user_id=user_id,
            actions=[
                LearningActionItem(action="delete_project", project_title="Old project"),
            ],
        )
    assert applied == 0
    delete_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_load_learning_classes_for_prompt():
    session = AsyncMock()
    project = _project("English")
    with (
        patch.object(
            learning_repo,
            "list_for_user",
            AsyncMock(return_value=[project]),
        ),
        patch.object(
            learning_items_repo,
            "list_for_user",
            AsyncMock(return_value=[_item("run", project.id)]),
        ),
    ):
        block = await learning_service.load_learning_classes_for_prompt(
            session, uuid4(), Settings()
        )
    assert "English" in block
    assert "○ run" not in block
    assert str(project.id) in block
    assert "learning_launch" in block
    assert "Do NOT run a quiz in this chat" in block
    assert "You ARE connected to their Recall Learning data" in block
    assert "progress only" in block


def test_format_learning_overview_block_omits_lemmas():
    project = _project("English")
    project.learning_path = ["Hello and goodbye", "Immediate family"]
    hello = _item("hello", project.id, list_title="Hello and goodbye")
    parent = _item("parent", project.id, list_title="Immediate family")
    block = learning_service.format_learning_overview_block([project], [hello, parent])
    assert "Current chapter: Hello and goodbye" in block
    assert "○ hello" not in block
    assert "○ parent" not in block
    assert "parent" not in block
    assert "Progress:" in block


def test_format_current_chapter_block_scopes_words():
    project = _project("English")
    project.learning_path = ["Hello and goodbye", "Immediate family"]
    hello = _item("hello", project.id, list_title="Hello and goodbye")
    parent = _item("parent", project.id, list_title="Immediate family")
    block = learning_service.format_current_chapter_block(project, [hello, parent])
    assert "Now: Hello and goodbye" in block
    assert "hello" in block
    assert "parent" not in block


@pytest.mark.asyncio
async def test_sync_learning_from_transcript_does_not_add_language_words():
    from app.gateways import mock_llm
    from app.services.learning import sync_learning_from_transcript

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
            learning_repo,
            "list_for_user",
            AsyncMock(return_value=[project]),
        ),
        # _load_learning_sync_snapshot (LLM-facing snapshot) still uses
        # list_for_user; apply_learning_actions' own dedup/match snapshot
        # uses list_recent_for_user (fix for the >500-item recency bug) —
        # both need mocking on this end-to-end path.
        patch.object(
            learning_items_repo,
            "list_for_user",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            learning_items_repo,
            "list_recent_for_learning",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            learning_items_repo,
            "create",
            AsyncMock(side_effect=lambda *a, **kw: _item(kw["content"], project.id)),
        ) as create_mock,
        patch.object(
            learning_items_repo,
            "count_for_project",
            AsyncMock(return_value=0),
        ),
        patch.object(mock_llm, "should_mock_llm", return_value=True),
    ):
        result = await sync_learning_from_transcript(
            settings,
            user_id=user_id,
            chat_id=chat_id,
            transcript=transcript,
        )

        assert result is not None
        assert len(result.actions) >= 3
        assert create_mock.await_count == 0


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
            learning_repo,
            "list_for_user",
            AsyncMock(return_value=[project]),
        ),
        _patch_count_stats_by_learning(
            {
                "total": 20,
                "mastered_today": 2,
                "pending_today": 0,
            }
        ),
    ):
        block = await learning_service.load_daily_learning_summary_for_prompt(
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
            learning_repo,
            "list_for_user",
            AsyncMock(return_value=[project]),
        ),
        _patch_count_stats_by_learning(
            {
                "total": 12,
                "mastered_today": 0,
                "pending_today": 0,
            }
        ),
    ):
        block = await learning_service.load_daily_learning_summary_for_prompt(
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
            learning_repo,
            "list_for_user",
            AsyncMock(return_value=[project]),
        ),
        _patch_count_stats_by_learning(
            {
                "total": 20,
                "mastered_today": 5,
                "pending_today": 0,
            }
        ),
    ):
        block = await learning_service.load_daily_learning_summary_for_prompt(
            session, user, Settings()
        )

    assert "Today's learning progress" in block
    assert "vocabulary quiz" in block
    assert "daily goal complete" in block
    assert "0/5" not in block
    assert "Only mention learning tracks listed above" in block


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_load_daily_learning_summary_no_active_class():
    """Deleted vocab class must not leave room for invented 0/N quiz stats."""
    session = AsyncMock()
    user = MagicMock()
    user.id = uuid4()
    user.timezone = "America/Los_Angeles"

    with patch.object(
        learning_repo,
        "list_for_user",
        AsyncMock(return_value=[]),
    ):
        block = await learning_service.load_daily_learning_summary_for_prompt(
            session, user, Settings()
        )

    assert "No active learning class" in block
    assert "Do not mention vocabulary quiz" in block


@pytest.mark.asyncio
async def test_load_daily_learning_summary_batches_stats():
    session = AsyncMock()
    user = MagicMock()
    user.id = uuid4()
    user.timezone = "UTC"
    english = _project("English · Beginner")
    english.daily_goal = 5
    spanish = _project("Spanish · Beginner")
    spanish.target_language = "es"
    spanish.daily_goal = 5
    general = _project("Research notes", kind="research")

    async def _mock(_session, project_ids, *, timezone_by_project=None):
        by_id = {
            english.id: {"total": 10, "mastered_today": 2, "pending_today": 0},
            spanish.id: {"total": 8, "mastered_today": 1, "pending_today": 0},
        }
        return {pid: by_id[pid] for pid in project_ids if pid in by_id}

    with (
        patch.object(
            learning_repo,
            "list_for_user",
            AsyncMock(return_value=[english, spanish, general]),
        ),
        patch(
            "app.services.learning.stats.count_stats_by_learning",
            AsyncMock(side_effect=_mock),
        ) as stats_mock,
    ):
        block = await learning_service.load_daily_learning_summary_for_prompt(
            session, user, Settings()
        )

    stats_mock.assert_awaited_once()
    assert set(stats_mock.await_args.args[1]) == {english.id, spanish.id}
    assert "English · Beginner" in block
    assert "Spanish · Beginner" in block


@pytest.mark.asyncio
async def test_load_today_learning_words_for_prompt():
    session = AsyncMock()
    user = MagicMock()
    user.id = uuid4()
    user.timezone = "America/Los_Angeles"
    project = _project("English · Beginner")
    mastered = _catalog_item(project.id, mastered=True)
    missed = _catalog_item(project.id, index=1)

    with (
        patch.object(
            learning_repo,
            "list_for_user",
            AsyncMock(return_value=[project]),
        ),
        patch.object(
            learning_items_repo,
            "list_by_activity_date",
            AsyncMock(return_value=[mastered]),
        ) as mastered_mock,
        patch.object(
            learning_items_repo,
            "list_missed_by_activity_date",
            AsyncMock(return_value=[missed]),
        ) as missed_mock,
    ):
        block = await learning_service.load_today_learning_words_for_prompt(
            session, user, Settings(), client_timezone="America/Los_Angeles"
        )

    mastered_mock.assert_awaited_once()
    missed_mock.assert_awaited_once()
    assert "Words from today's session" in block
    assert mastered.content in block
    assert missed.content in block
    assert "You ARE connected" in block
    assert "not connected to their learning app" in block


@pytest.mark.asyncio
async def test_load_today_learning_words_no_practice_yet():
    session = AsyncMock()
    user = MagicMock()
    user.id = uuid4()
    user.timezone = "UTC"
    project = _project("English · Beginner")

    with (
        patch.object(
            learning_repo,
            "list_for_user",
            AsyncMock(return_value=[project]),
        ),
        patch.object(
            learning_items_repo,
            "list_by_activity_date",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            learning_items_repo,
            "list_missed_by_activity_date",
            AsyncMock(return_value=[]),
        ),
    ):
        block = await learning_service.load_today_learning_words_for_prompt(
            session, user, Settings()
        )

    assert "no words practiced today yet" in block
    assert "You ARE connected" in block


@pytest.mark.asyncio
async def test_load_today_learning_words_no_active_class():
    session = AsyncMock()
    user = MagicMock()
    user.id = uuid4()
    user.timezone = "UTC"

    with patch.object(
        learning_repo,
        "list_for_user",
        AsyncMock(return_value=[]),
    ):
        block = await learning_service.load_today_learning_words_for_prompt(
            session, user, Settings()
        )

    assert "No active learning class" in block
    assert "You ARE connected" in block


@pytest.mark.asyncio
async def test_load_learning_for_prompt_scoped():
    session = AsyncMock()
    user_id = uuid4()
    project_id = uuid4()
    project = _project("Spanish")
    project.id = project_id
    project.target_language = "es"
    item = _catalog_item(project_id, language="es")

    with (
        patch.object(
            learning_repo,
            "get_by_id",
            AsyncMock(return_value=project),
        ),
        patch.object(
            learning_items_repo,
            "list_for_user",
            AsyncMock(return_value=[item]),
        ) as list_items,
        patch.object(
            learning_items_repo,
            "list_quiz_exclusion_contents",
            AsyncMock(return_value=[]),
        ),
    ):
        block = await learning_service.load_learning_for_prompt(
            session, user_id, project_id, Settings()
        )

    assert "linked to ONE learning topic" in block
    assert "Spanish" in block
    assert item.content in block
    list_items.assert_awaited_once()


@pytest.mark.asyncio
async def test_load_learning_for_prompt_current_chapter_only():
    session = AsyncMock()
    user_id = uuid4()
    project_id = uuid4()
    project = _project("English")
    project.id = project_id
    hello = _catalog_item(project_id)
    parent = _catalog_item(project_id, chapter=1)
    project.learning_path = [hello.list_title, parent.list_title]

    with (
        patch.object(
            learning_repo,
            "get_by_id",
            AsyncMock(return_value=project),
        ),
        patch.object(
            learning_items_repo,
            "list_for_user",
            AsyncMock(return_value=[hello, parent]),
        ),
    ):
        block = await learning_service.load_learning_for_prompt(
            session, user_id, project_id, Settings()
        )

    assert hello.content in block
    assert parent.content not in block
    assert f"Now: {hello.list_title}" in block


@pytest.mark.asyncio
async def test_load_learning_for_prompt_chat_mode():
    session = AsyncMock()
    user_id = uuid4()
    project_id = uuid4()
    project = _project("English")
    project.id = project_id

    with (
        patch.object(
            learning_repo,
            "get_by_id",
            AsyncMock(return_value=project),
        ),
        patch.object(
            learning_items_repo,
            "list_for_user",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            learning_items_repo,
            "list_quiz_exclusion_contents",
            AsyncMock(return_value=[]),
        ),
    ):
        block = await learning_service.load_learning_for_prompt(
            session, user_id, project_id, Settings(), quiz_mode="chat"
        )

    assert "Do NOT run a quiz in this chat" in block
    assert "learning_launch" in block
    assert "Presentation mode: chat" in block
    assert "multiple choice only" not in block.lower()


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_load_learning_for_prompt_uses_chat_mode_even_when_exam_requested():
    session = AsyncMock()
    user_id = uuid4()
    project_id = uuid4()
    project = _project("English")
    project.id = project_id

    with (
        patch.object(
            learning_repo,
            "get_by_id",
            AsyncMock(return_value=project),
        ),
        patch.object(
            learning_items_repo,
            "list_for_user",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            learning_items_repo,
            "list_quiz_exclusion_contents",
            AsyncMock(return_value=[]),
        ),
    ):
        block = await learning_service.load_learning_for_prompt(
            session, user_id, project_id, Settings(), quiz_mode="exam"
        )

    assert "presentation mode: chat" in block.lower()
    assert "learning_launch" in block.lower()
    assert "exam (legacy)" not in block.lower()


def test_format_covered_quiz_lines_bans_mastered_and_just_answered():
    lines = learning_prompt_context._format_covered_quiz_lines(
        ["apple", "banana"],
        just_answered="cherry",
        max_chars=10_000,
    )
    text = "\n".join(lines)
    assert "Already mastered" in text
    assert "do not quiz these in chat" in text
    assert "- cherry" in text
    assert "- apple" in text
    assert "- banana" in text


def test_format_covered_quiz_lines_dedupes_case_and_caps():
    lines = learning_prompt_context._format_covered_quiz_lines(
        ["Apple", "apple", "Banana"] + [f"word{i}" for i in range(50)],
        just_answered="APPLE",
        max_chars=40,
    )
    text = "\n".join(lines)
    assert text.count("- apple") + text.count("- Apple") + text.count("- APPLE") == 1
    assert "more mastered items not listed" in text


def test_format_failed_review_lines_prioritizes_due_misses():
    from datetime import UTC, datetime, timedelta

    from app.models.orm import LearningItem

    older = MagicMock(spec=LearningItem)
    older.content = "ephemeral"
    older.status = "learning"
    older.last_incorrect_at = datetime.now(UTC) - timedelta(days=1)
    older.due_at = datetime.now(UTC) - timedelta(hours=1)

    newer = MagicMock(spec=LearningItem)
    newer.content = "quintessential"
    newer.status = "learning"
    newer.last_incorrect_at = datetime.now(UTC)
    newer.due_at = datetime.now(UTC) + timedelta(days=1)

    fresh = MagicMock(spec=LearningItem)
    fresh.content = "serendipity"
    fresh.status = "new"
    fresh.last_incorrect_at = None
    fresh.due_at = None

    legacy = MagicMock(spec=LearningItem)
    legacy.content = "ubiquitous"
    legacy.status = "learning"
    legacy.last_incorrect_at = datetime.now(UTC) - timedelta(days=2)
    legacy.due_at = None

    lines = learning_prompt_context._format_failed_review_lines([fresh, older, newer, legacy])
    joined = "\n".join(lines)
    assert "Due for review in the lesson" in joined
    assert "ephemeral" in joined
    assert "ubiquitous" in joined
    assert "quintessential" not in joined
    assert "serendipity" not in joined
    assert joined.index("ephemeral") < joined.index("ubiquitous")


def test_group_items_and_build_stats():
    project_id = uuid4()
    items = [
        _item("alpha", project_id, list_title="Basics"),
        _item("beta", project_id, list_title="Basics", mastered=True),
    ]
    groups = learning_service.group_items(items)
    assert len(groups) == 1
    assert groups[0].list_title == "Basics"
    assert len(groups[0].items) == 2

    stats = learning_service.build_stats(items)
    assert stats.total == 2
    assert stats.mastered_count == 1
    assert stats.new_count == 1


def test_format_learning_block_empty_items():
    project = _project("Empty")
    block = learning_service.format_learning_block([project], [])
    assert "(no words yet)" in block


def test_stats_for_items_matches_repository_stats_for_due_for_review():
    """The prompt-side _stats_for_items must delegate to the repository's
    stats_from_items so the model sees the same due_for_review count the
    mobile UI renders. Previously _stats_for_items reimplemented the logic
    with two divergences (counted `new` items as due; used last_reviewed_at
    instead of due_at), so the prompt claimed a different review queue."""
    from datetime import UTC, datetime, timedelta

    from app.services.learning.stats import stats_from_items

    now = datetime.now(UTC)
    project = _project("English")

    # Mix of items that exercise both divergences:
    # - a `new` item (prompt used to count as due; API does not)
    # - a `learning` item with due_at in the past (API counts as due)
    # - a `learning` item reviewed recently (neither counts as due)
    # - a `mastered` item (neither counts as due)
    new_item = _item("apple", project.id)
    new_item.status = "new"
    new_item.mastered = False
    new_item.created_at = now
    new_item.due_at = None
    new_item.last_reviewed_at = None
    new_item.mastered_at = None
    new_item.last_incorrect_at = None

    learning_due = _item("banana", project.id)
    learning_due.status = "learning"
    learning_due.mastered = False
    learning_due.created_at = now - timedelta(days=3)
    learning_due.due_at = now - timedelta(hours=1)
    learning_due.last_reviewed_at = now - timedelta(hours=2)
    learning_due.mastered_at = None
    learning_due.last_incorrect_at = None

    learning_recent = _item("cherry", project.id)
    learning_recent.status = "learning"
    learning_recent.mastered = False
    learning_recent.created_at = now - timedelta(days=3)
    learning_recent.due_at = now + timedelta(hours=12)
    learning_recent.last_reviewed_at = now - timedelta(minutes=30)
    learning_recent.mastered_at = None
    learning_recent.last_incorrect_at = None

    mastered = _item("date", project.id, mastered=True)
    mastered.status = "mastered"
    mastered.created_at = now - timedelta(days=10)
    mastered.due_at = None
    mastered.last_reviewed_at = now - timedelta(days=5)
    mastered.mastered_at = now - timedelta(days=5)
    mastered.last_incorrect_at = None

    items = [new_item, learning_due, learning_recent, mastered]
    prompt_stats = learning_prompt_context._stats_for_items(items)
    repo_stats = stats_from_items(items)

    assert prompt_stats["due_for_review"] == repo_stats["due_for_review"]
    # Both the learning item and the mastered word with an overdue review count.
    assert repo_stats["due_for_review"] == 2


@pytest.mark.asyncio
async def test_apply_learning_actions_skips_master_after_recent_miss():
    from datetime import UTC, datetime

    session = AsyncMock()
    user_id = uuid4()
    project = _project("English")
    existing = _item("luminous", project.id)
    existing.status = "learning"
    existing.last_incorrect_at = datetime.now(UTC)

    with (
        patch.object(
            learning_repo,
            "list_for_user",
            AsyncMock(return_value=[project]),
        ),
        patch.object(
            learning_items_repo,
            "list_recent_for_learning",
            AsyncMock(return_value=[existing]),
        ),
        patch.object(
            learning_items_repo,
            "update",
            AsyncMock(return_value=existing),
        ) as update_mock,
    ):
        applied = await learning_service.apply_learning_actions(
            session,
            user_id=user_id,
            actions=[
                LearningActionItem(
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
async def test_apply_learning_actions_start_learning_and_unmaster():
    session = AsyncMock()
    user_id = uuid4()
    project = _project("English")
    existing = _item("apple", project.id, mastered=True)
    existing.status = "mastered"

    with (
        patch.object(
            learning_repo,
            "list_for_user",
            AsyncMock(return_value=[project]),
        ),
        patch.object(
            learning_items_repo,
            "list_recent_for_learning",
            AsyncMock(return_value=[existing]),
        ),
        patch.object(
            learning_items_repo,
            "update",
            AsyncMock(return_value=existing),
        ) as update_mock,
    ):
        applied = await learning_service.apply_learning_actions(
            session,
            user_id=user_id,
            actions=[
                LearningActionItem(
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
async def test_apply_learning_actions_start_learning_records_failed_quiz():
    session = AsyncMock()
    user_id = uuid4()
    project = _project("English")
    existing = _item("serendipity", project.id)
    existing.status = "new"
    existing.last_incorrect_at = None

    with (
        patch.object(
            learning_repo,
            "list_for_user",
            AsyncMock(return_value=[project]),
        ),
        patch.object(
            learning_items_repo,
            "list_recent_for_learning",
            AsyncMock(return_value=[existing]),
        ),
        patch(
            "app.services.learning.quiz_grading.apply_quiz_result",
            AsyncMock(return_value=existing),
        ) as apply_result,
    ):
        applied = await learning_service.apply_learning_actions(
            session,
            user_id=user_id,
            actions=[
                LearningActionItem(
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
async def test_apply_learning_actions_delete_list():
    """from_transcript=False simulates an explicit user-initiated caller —
    see test_apply_learning_actions_delete_project."""
    session = AsyncMock()
    user_id = uuid4()
    project = _project("English")
    with (
        patch.object(
            learning_repo,
            "list_for_user",
            AsyncMock(return_value=[project]),
        ),
        patch.object(
            learning_items_repo,
            "list_recent_for_learning",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            learning_items_repo,
            "delete_by_list",
            AsyncMock(return_value=2),
        ) as delete_mock,
    ):
        applied = await learning_service.apply_learning_actions(
            session,
            user_id=user_id,
            actions=[
                LearningActionItem(
                    action="delete_list",
                    project_title="English",
                    list_title="Travel",
                ),
            ],
            from_transcript=False,
        )
    assert applied == 1
    delete_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_apply_learning_actions_blocks_delete_list_by_default():
    session = AsyncMock()
    user_id = uuid4()
    project = _project("English")
    with (
        patch.object(
            learning_repo,
            "list_for_user",
            AsyncMock(return_value=[project]),
        ),
        patch.object(
            learning_items_repo,
            "list_recent_for_learning",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            learning_items_repo,
            "delete_by_list",
            AsyncMock(return_value=2),
        ) as delete_mock,
    ):
        applied = await learning_service.apply_learning_actions(
            session,
            user_id=user_id,
            actions=[
                LearningActionItem(
                    action="delete_list",
                    project_title="English",
                    list_title="Travel",
                ),
            ],
        )
    assert applied == 0
    delete_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_learning_actions_set_description():
    session = AsyncMock()
    user_id = uuid4()
    project = _project("English")
    with (
        patch.object(
            learning_repo,
            "list_for_user",
            AsyncMock(return_value=[project]),
        ),
        patch.object(
            learning_items_repo,
            "list_recent_for_learning",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            learning_repo,
            "update",
            AsyncMock(return_value=project),
        ) as update_mock,
    ):
        applied = await learning_service.apply_learning_actions(
            session,
            user_id=user_id,
            actions=[
                LearningActionItem(
                    action="set_description",
                    project_title="English",
                    description="Travel vocab",
                ),
            ],
        )
    assert applied == 1
    assert update_mock.await_count == 1


@pytest.mark.asyncio
async def test_apply_learning_actions_skips_duplicate_add():
    session = AsyncMock()
    user_id = uuid4()
    project = _project("English")
    existing = _item("apple", project.id)
    with (
        patch.object(
            learning_repo,
            "list_for_user",
            AsyncMock(return_value=[project]),
        ),
        patch.object(
            learning_items_repo,
            "list_recent_for_learning",
            AsyncMock(return_value=[existing]),
        ),
        patch.object(
            learning_items_repo,
            "create",
            AsyncMock(),
        ) as create_mock,
    ):
        applied = await learning_service.apply_learning_actions(
            session,
            user_id=user_id,
            actions=[
                LearningActionItem(
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
async def test_apply_learning_actions_delete_does_not_fuzzy_match_substring():
    """BUG FIX regression: deck has "category" but not "cat" — a delete for
    "cat" must no-op, not fall back to substring-matching "category"."""
    session = AsyncMock()
    user_id = uuid4()
    project = _project("English")
    existing = _item("category", project.id)
    with (
        patch.object(
            learning_repo,
            "list_for_user",
            AsyncMock(return_value=[project]),
        ),
        patch.object(
            learning_items_repo,
            "list_recent_for_learning",
            AsyncMock(return_value=[existing]),
        ),
        patch.object(
            learning_items_repo,
            "delete_by_id",
            AsyncMock(),
        ) as delete_mock,
    ):
        applied = await learning_service.apply_learning_actions(
            session,
            user_id=user_id,
            actions=[
                LearningActionItem(
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
async def test_apply_learning_actions_master_does_not_fuzzy_match_substring():
    """Same false-positive-match bug for `master` — "cat" must not resolve
    to an existing "category" item."""
    session = AsyncMock()
    user_id = uuid4()
    project = _project("English")
    existing = _item("category", project.id)
    with (
        patch.object(
            learning_repo,
            "list_for_user",
            AsyncMock(return_value=[project]),
        ),
        patch.object(
            learning_items_repo,
            "list_recent_for_learning",
            AsyncMock(return_value=[existing]),
        ),
        patch.object(
            learning_items_repo,
            "update",
            AsyncMock(),
        ) as update_mock,
    ):
        applied = await learning_service.apply_learning_actions(
            session,
            user_id=user_id,
            actions=[
                LearningActionItem(
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
async def test_apply_learning_actions_master_not_skipped_as_fuzzy_duplicate():
    """Deck has "category" and "cat" — mastering "cat" must not hit "category"."""
    session = AsyncMock()
    user_id = uuid4()
    project = _project("English")
    category = _item("category", project.id, list_title="nouns")
    cat = _item("cat", project.id, list_title="nouns")
    with (
        patch.object(
            learning_repo,
            "list_for_user",
            AsyncMock(return_value=[project]),
        ),
        patch.object(
            learning_items_repo,
            "list_recent_for_learning",
            AsyncMock(return_value=[category, cat]),
        ),
        patch(
            "app.services.learning.items.update_item",
            AsyncMock(return_value=cat),
        ) as update_mock,
    ):
        applied = await learning_service.apply_learning_actions(
            session,
            user_id=user_id,
            actions=[
                LearningActionItem(
                    action="master",
                    project_title="English",
                    list_title="nouns",
                    content="cat",
                ),
            ],
        )
    assert applied == 1
    update_mock.assert_awaited_once()
    assert update_mock.await_args.args[1] is cat


@pytest.mark.asyncio
async def test_apply_learning_actions_add_skipped_for_language_catalog():
    session = AsyncMock()
    user_id = uuid4()
    project = _project("Spanish")
    with (
        patch.object(
            learning_repo,
            "list_for_user",
            AsyncMock(return_value=[project]),
        ),
        patch.object(
            learning_items_repo,
            "list_recent_for_learning",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            learning_items_repo,
            "create",
            AsyncMock(),
        ) as create_mock,
    ):
        applied = await learning_service.apply_learning_actions(
            session,
            user_id=user_id,
            actions=[
                LearningActionItem(
                    action="add",
                    project_title="Spanish",
                    list_title="Greetings",
                    content="invented",
                ),
            ],
        )
    assert applied == 0
    create_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_project_extraction_result_blocks_destructive_actions():
    """LEARNING_BLOCKED_FROM_TRANSCRIPT is what stops the LLM from deleting a
    whole project/list via chat. Nothing previously exercised
    _apply_project_extraction_result itself or asserted a delete_project /
    delete_list action from LLM extraction never reaches the repo layer —
    this asserts the repo deletes are never called, while a legitimate
    non-destructive action in the same extraction result still applies."""
    from app.models.schemas import LearningExtractionResult

    session = AsyncMock()
    user_id = uuid4()
    chat_id = uuid4()
    project = _project("English")
    apple = _item("apple", project.id, list_title="nouns")
    result = LearningExtractionResult(
        actions=[
            LearningActionItem(action="delete_project", project_title="English"),
            LearningActionItem(
                action="master", project_title="English", list_title="nouns", content="apple"
            ),
            LearningActionItem(action="delete_list", project_title="English", list_title="Travel"),
        ]
    )
    with (
        patch.object(
            learning_repo,
            "list_for_user",
            AsyncMock(return_value=[project]),
        ),
        patch.object(
            learning_items_repo,
            "list_recent_for_learning",
            AsyncMock(return_value=[apple]),
        ),
        patch.object(
            learning_repo,
            "delete_by_id",
            AsyncMock(return_value=True),
        ) as delete_project_mock,
        patch.object(
            learning_items_repo,
            "delete_by_list",
            AsyncMock(return_value=2),
        ) as delete_list_mock,
        patch(
            "app.services.learning.items.update_item",
            AsyncMock(return_value=apple),
        ) as update_mock,
    ):
        applied = await learning_sync._apply_project_extraction_result(
            session, user_id=user_id, chat_id=chat_id, result=result
        )

    assert applied == 1
    delete_project_mock.assert_not_awaited()
    delete_list_mock.assert_not_awaited()
    update_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_apply_project_extraction_result_caps_actions_per_turn():
    """More than MAX_LEARNING_ACTIONS_PER_TURN actions in one extraction
    result must only have the cap's worth applied."""
    from app.models.schemas import LearningExtractionResult

    session = AsyncMock()
    user_id = uuid4()
    chat_id = uuid4()
    project = _project("English")
    over_cap = learning_service.MAX_LEARNING_ACTIONS_PER_TURN + 2
    items = [_item(f"word{i}", project.id, list_title="nouns") for i in range(over_cap)]
    result = LearningExtractionResult(
        actions=[
            LearningActionItem(
                action="master", project_title="English", list_title="nouns", content=f"word{i}"
            )
            for i in range(over_cap)
        ]
    )
    with (
        patch.object(
            learning_repo,
            "list_for_user",
            AsyncMock(return_value=[project]),
        ),
        patch.object(
            learning_items_repo,
            "list_recent_for_learning",
            AsyncMock(return_value=items),
        ),
        patch(
            "app.services.learning.items.update_item",
            AsyncMock(side_effect=lambda *a, **kw: a[1] if a else None),
        ) as update_mock,
    ):
        applied = await learning_sync._apply_project_extraction_result(
            session, user_id=user_id, chat_id=chat_id, result=result
        )

    assert applied == learning_service.MAX_LEARNING_ACTIONS_PER_TURN
    assert update_mock.await_count == learning_service.MAX_LEARNING_ACTIONS_PER_TURN


@pytest.mark.asyncio
async def test_sync_learning_from_transcript_applies_litellm_actions():
    from app.models.schemas import LearningExtractionResult

    session = AsyncMock()
    user_id = uuid4()
    chat_id = uuid4()
    project = _project("English")
    settings = Settings()

    extraction = LearningExtractionResult(
        actions=[
            LearningActionItem(
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
            learning_repo,
            "list_for_user",
            AsyncMock(return_value=[project]),
        ),
        # apply_learning_actions is mocked below, so only
        # _load_learning_sync_snapshot's list_for_user call is exercised here.
        patch.object(
            learning_items_repo,
            "list_for_user",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.learning.extract.extract_learning_actions",
            AsyncMock(return_value=extraction),
        ),
        patch.object(
            learning_service,
            "apply_learning_actions",
            AsyncMock(return_value=1),
        ) as apply_mock,
    ):
        result = await learning_service.sync_learning_from_transcript(
            settings,
            user_id=user_id,
            chat_id=chat_id,
            transcript="add world",
        )

    assert result is extraction
    apply_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_sync_learning_from_transcript_releases_db_before_llm():
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
        patch.object(learning_repo, "list_for_user", AsyncMock(return_value=[])),
        # fake_extract always returns None, so apply_learning_actions is never
        # reached — only _load_learning_sync_snapshot's list_for_user call is
        # exercised here.
        patch.object(
            learning_items_repo,
            "list_for_user",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.learning.extract.extract_learning_actions",
            AsyncMock(side_effect=fake_extract),
        ),
    ):
        await learning_service.sync_learning_from_transcript(
            Settings(),
            user_id=uuid4(),
            chat_id=uuid4(),
            transcript="add word",
        )

    assert db_open_during_extract == [False]
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_sync_learning_from_transcript_returns_none_on_error():
    session = AsyncMock()
    settings = Settings()

    with (
        patch(
            "app.core.db.SessionLocal",
            side_effect=_session_local_side_effect(session),
        ),
        patch.object(
            learning_repo,
            "list_for_user",
            AsyncMock(return_value=[]),
        ),
        # extract_learning_actions raises below, so apply_learning_actions is
        # never reached — only _load_learning_sync_snapshot's list_for_user
        # call is exercised here.
        patch.object(
            learning_items_repo,
            "list_for_user",
            AsyncMock(return_value=[]),
        ),
        patch.object(
            learning_items_repo,
            "list_quiz_exclusion_contents",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.learning.extract.extract_learning_actions",
            AsyncMock(side_effect=RuntimeError("boom")),
        ),
    ):
        result = await learning_service.sync_learning_from_transcript(
            settings,
            user_id=uuid4(),
            chat_id=uuid4(),
            transcript="add word",
        )

    assert result is None


def test_language_tutor_hint_uses_target_language():
    from app.services.learning import language_tutor_hint

    hint = language_tutor_hint("es")
    assert "Spanish vocabulary" in hint
    assert "skill level" not in hint
    assert "Do NOT run a quiz in this chat" in hint
    assert "learning_launch" in hint


def test_chat_learning_handoff_hint_forbids_in_chat_quiz():
    from app.services.learning import CHAT_LEARNING_HANDOFF_HINT

    assert "learning_launch" in CHAT_LEARNING_HANDOFF_HINT
    assert "Do NOT run a quiz in this chat" in CHAT_LEARNING_HANDOFF_HINT
    assert "vocab_quiz" in CHAT_LEARNING_HANDOFF_HINT
    assert "You ARE connected to their Recall Learning data" in CHAT_LEARNING_HANDOFF_HINT


def test_chat_tutor_hints_acknowledge_completed_daily_goal():
    """When the daily goal is already met, chat must not quiz — congratulate
    and hand off to the lesson if they want more practice."""
    from app.services.learning import DAILY_GOAL_COMPLETE_BEHAVIOR, language_tutor_hint

    assert DAILY_GOAL_COMPLETE_BEHAVIOR in language_tutor_hint("en")
    # The behaviour must explicitly handle the "let's continue" case.
    assert "let's continue" in DAILY_GOAL_COMPLETE_BEHAVIOR.lower()
    assert "raise their daily goal" in DAILY_GOAL_COMPLETE_BEHAVIOR.lower()
