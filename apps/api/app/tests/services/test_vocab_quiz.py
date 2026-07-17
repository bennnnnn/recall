import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import projects as projects_service
from app.services import vocab_quiz as vocab_quiz_service
from app.services.projects import quiz_context as projects_quiz_context

TRIVIA_FENCE = (
    "```vocab_quiz\n"
    '{"quiz_type":"trivia","word":"History",'
    '"question":"Which wonder stood at Rhodes?",'
    '"correct":"A",'
    '"choices":['
    '{"letter":"A","text":"Colossus"},'
    '{"letter":"B","text":"Pyramid"},'
    '{"letter":"C","text":"Lighthouse"},'
    '{"letter":"D","text":"Mausoleum"}'
    "]}\n"
    "```"
)


def test_parse_trivia_quiz_fence():
    quiz = vocab_quiz_service.parse_vocab_quiz(TRIVIA_FENCE)
    assert quiz is not None
    assert quiz.quiz_type == "trivia"
    assert quiz.word == "History"
    assert quiz.question == "Which wonder stood at Rhodes?"
    assert quiz.correct == "A"
    assert quiz.correct_text == "Colossus"


def test_format_quiz_grading_hint_trivia_uses_answer_not_topic():
    from app.services.chat.prompt_constants import format_quiz_grading_hint

    hint = format_quiz_grading_hint(
        is_correct=True,
        user_letter="A",
        correct_letter="A",
        word="Treaty of Versailles",
        quiz_type="trivia",
        question="Which treaty officially ended World War I?",
    )
    assert "Treaty of Versailles" in hint
    assert "History is correct" not in hint
    assert "Do NOT ask" in hint
    assert "Which treaty officially ended World War I?" in hint
    assert "quiz_type" in hint
    assert "What does X mean?" in hint


def test_format_covered_quiz_lines_bans_ledger_and_just_answered():
    lines = projects_quiz_context._format_covered_quiz_lines(
        ["apple", "banana"],
        just_answered="cherry",
    )
    text = "\n".join(lines)
    assert "Do NOT ask these again" in text
    assert "quiz ledger" in text
    assert "- cherry" in text
    assert "- apple" in text
    assert "- banana" in text


def test_format_covered_quiz_lines_dedupes_case_and_caps():
    lines = projects_quiz_context._format_covered_quiz_lines(
        ["Apple", "apple", "Banana"] + [f"word{i}" for i in range(50)],
        just_answered="APPLE",
        limit=5,
    )
    text = "\n".join(lines)
    assert text.count("- apple") + text.count("- Apple") + text.count("- APPLE") == 1
    assert "more ledger items not listed" in text


@pytest.mark.asyncio
async def test_load_trivia_quiz_context_correct_bans_repeat():
    from app.core.config import Settings
    from app.models.orm import Project
    from app.services.vocab_quiz import QuizAnswerGrade

    session = AsyncMock()
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    project = Project(
        id=project_id,
        user_id=user_id,
        title="General knowledge",
        kind="trivia",
        level="level3",
        target_language="en",
        daily_goal=10,
    )
    covered = MagicMock()
    covered.content = "Which treaty officially ended World War I?"
    covered.status = "mastered"
    covered.mastered = True
    covered.mastered_at = None
    covered.last_reviewed_at = None
    covered.created_at = None
    covered.definition = None
    covered.note = None
    covered.example_sentence = None
    covered.last_incorrect_at = None

    with (
        patch(
            "app.repositories.projects.get_by_id",
            new=AsyncMock(return_value=project),
        ),
        patch(
            "app.repositories.project_items.list_for_user",
            new=AsyncMock(return_value=[covered]),
        ),
        patch(
            "app.repositories.project_items.list_quiz_exclusion_contents",
            new=AsyncMock(return_value=["Which treaty officially ended World War I?"]),
        ),
    ):
        block = await projects_service.load_project_quiz_context(
            session,
            user_id,
            project_id,
            Settings(),
            quiz_grade=QuizAnswerGrade(
                is_correct=True,
                user_letter="A",
                correct_letter="A",
                word="Treaty of Versailles",
                quiz_type="trivia",
                question="Which treaty officially ended World War I?",
            ),
        )

    assert "CORRECT" in block
    assert "Do NOT repeat" in block
    assert "Do NOT ask these again" in block
    assert "quiz ledger" in block
    assert "Which treaty officially ended World War I?" in block
    assert "WRONG" not in block
    assert "prioritize revisiting" not in block


def test_format_quiz_grading_hint_exhausted_moves_on():
    from app.services.chat.prompt_constants import format_quiz_grading_hint

    hint = format_quiz_grading_hint(
        is_correct=False,
        user_letter="D",
        correct_letter="A",
        word="Thirty Years' War",
        quiz_type="trivia",
        question="Which war ended with the Treaty of Westphalia in 1648?",
        attempt=3,
        tries_exhausted=True,
    )
    assert "FAILED" in hint
    assert "Thirty Years' War" in hint
    assert "DIFFERENT" in hint
    assert "redisplay" not in hint.lower() or "Do NOT redisplay" not in hint


@pytest.mark.asyncio
async def test_apply_deterministic_marks_tries_exhausted_on_third_wrong():
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
            "app.repositories.projects.get_by_id",
            new=AsyncMock(return_value=project),
        ),
        patch(
            "app.repositories.project_items.find_quiz_candidates",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.projects.quiz_grading.create_item",
            new=AsyncMock(),
        ),
        patch(
            "app.services.projects.quiz_grading.apply_quiz_result",
            new=AsyncMock(),
        ),
    ):
        grade = await projects_service.apply_deterministic_quiz_answer(
            session,
            user_id=user_id,
            chat_id=uuid.uuid4(),
            project_id=project_id,
            assistant_content=TRIVIA_FENCE,
            user_answer="B",
            attempt=3,
        )

    assert grade is not None
    assert grade.is_correct is False
    assert grade.attempt == 3
    assert grade.tries_exhausted is True


@pytest.mark.asyncio
async def test_apply_deterministic_wrong_before_limit_not_exhausted():
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
    apply_result = AsyncMock()

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
            "app.services.projects.quiz_grading.create_item",
            new=AsyncMock(),
        ),
        patch(
            "app.services.projects.quiz_grading.apply_quiz_result",
            new=apply_result,
        ),
    ):
        grade = await projects_service.apply_deterministic_quiz_answer(
            session,
            user_id=user_id,
            chat_id=uuid.uuid4(),
            project_id=project_id,
            assistant_content=TRIVIA_FENCE,
            user_answer="B",
            attempt=2,
        )

    assert grade is not None
    assert grade.is_correct is False
    assert grade.tries_exhausted is False
    assert grade.attempt == 2
    apply_result.assert_not_called()


@pytest.mark.asyncio
async def test_apply_deterministic_persists_free_text_miss_on_third_try():
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
    apply_result = AsyncMock()
    create_item = AsyncMock(return_value=MagicMock())

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
            "app.services.projects.quiz_grading.create_item",
            new=create_item,
        ),
        patch(
            "app.services.projects.quiz_grading.apply_quiz_result",
            new=apply_result,
        ),
    ):
        grade = await projects_service.apply_deterministic_quiz_answer(
            session,
            user_id=user_id,
            chat_id=uuid.uuid4(),
            project_id=project_id,
            assistant_content=TRIVIA_FENCE,
            user_answer="Pyramid",
            attempt=3,
        )

    assert grade is not None
    assert grade.is_correct is False
    assert grade.user_letter == "B"
    assert grade.tries_exhausted is True
    create_item.assert_awaited()
    apply_result.assert_awaited()
    assert apply_result.await_args.kwargs["is_correct"] is False


def test_quiz_answer_letter_matches_choice_text():
    choices = (("A", "a typical example"), ("B", "lasting a short time"))
    assert vocab_quiz_service.quiz_answer_letter("lasting a short time", choices=choices) == "B"
    assert vocab_quiz_service.quiz_answer_letter("A typical example", choices=choices) == "A"
    assert vocab_quiz_service.quiz_answer_letter("hello", choices=choices) is None


def test_format_failed_review_lines_prioritizes_due_misses():
    from datetime import UTC, datetime, timedelta

    from app.models.orm import ProjectItem

    older = MagicMock(spec=ProjectItem)
    older.content = "ephemeral"
    older.status = "learning"
    older.last_incorrect_at = datetime.now(UTC) - timedelta(days=1)
    older.due_at = datetime.now(UTC) - timedelta(hours=1)

    newer = MagicMock(spec=ProjectItem)
    newer.content = "quintessential"
    newer.status = "learning"
    newer.last_incorrect_at = datetime.now(UTC)
    newer.due_at = datetime.now(UTC) + timedelta(days=1)

    fresh = MagicMock(spec=ProjectItem)
    fresh.content = "serendipity"
    fresh.status = "new"
    fresh.last_incorrect_at = None
    fresh.due_at = None

    legacy = MagicMock(spec=ProjectItem)
    legacy.content = "ubiquitous"
    legacy.status = "learning"
    legacy.last_incorrect_at = datetime.now(UTC) - timedelta(days=2)
    legacy.due_at = None

    lines = projects_quiz_context._format_failed_review_lines([fresh, older, newer, legacy])
    joined = "\n".join(lines)
    assert "Failed and due for review" in joined
    assert "ephemeral" in joined
    assert "ubiquitous" in joined
    assert "quintessential" not in joined
    assert "serendipity" not in joined
    assert joined.index("ephemeral") < joined.index("ubiquitous")


def test_quiz_answer_letter():
    assert vocab_quiz_service.quiz_answer_letter("B") == "B"
    assert vocab_quiz_service.quiz_answer_letter("c.") == "C"
    assert vocab_quiz_service.quiz_answer_letter("Is it a?") == "A"
    assert vocab_quiz_service.quiz_answer_letter("I think B") == "B"
    assert vocab_quiz_service.quiz_answer_letter("A bit more help") is None
    assert vocab_quiz_service.quiz_answer_letter("hello") is None


def test_is_vocab_quiz_answer():
    assert vocab_quiz_service.is_vocab_quiz_answer("Is it a?") is True
    assert vocab_quiz_service.is_vocab_quiz_answer("A bit more") is False
    assert vocab_quiz_service.is_vocab_quiz_answer("hello") is False


def test_parse_vocab_quiz_requires_correct_letter():
    # Uses 4 choices so it's only rejected for missing `correct`, not for choice count.
    fence = (
        "```vocab_quiz\n"
        '{"word":"cat","choices":['
        '{"letter":"A","text":"x"},{"letter":"B","text":"y"},'
        '{"letter":"C","text":"z"},{"letter":"D","text":"w"}'
        "]}\n"
        "```"
    )
    assert vocab_quiz_service.parse_vocab_quiz(fence) is None


def test_parse_vocab_quiz_rejects_fewer_than_four_choices():
    """The mobile parser (parseVocabQuiz.ts) rejects < 4 choices; the backend
    must match so a 2-3 choice quiz is never accepted server-side only to
    leave the mobile stuck on an un-answerable card."""
    two = (
        "```vocab_quiz\n"
        '{"word":"cat","correct":"A",'
        '"choices":[{"letter":"A","text":"x"},{"letter":"B","text":"y"}]}\n'
        "```"
    )
    three = (
        "```vocab_quiz\n"
        '{"word":"cat","correct":"A",'
        '"choices":[{"letter":"A","text":"x"},{"letter":"B","text":"y"},'
        '{"letter":"C","text":"z"}]}\n'
        "```"
    )
    assert vocab_quiz_service.parse_vocab_quiz(two) is None
    assert vocab_quiz_service.parse_vocab_quiz(three) is None


def test_parse_vocab_quiz_accepts_four_choices():
    four = (
        "```vocab_quiz\n"
        '{"word":"cat","correct":"A",'
        '"choices":['
        '{"letter":"A","text":"x"},{"letter":"B","text":"y"},'
        '{"letter":"C","text":"z"},{"letter":"D","text":"w"}'
        "]}\n"
        "```"
    )
    quiz = vocab_quiz_service.parse_vocab_quiz(four)
    assert quiz is not None
    assert len(quiz.choices) == 4


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
        "app.repositories.projects.get_by_id",
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
        "app.repositories.projects.get_by_id",
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


@pytest.mark.asyncio
async def test_load_trivia_quiz_context_exhausted_moves_on():
    from app.core.config import Settings
    from app.models.orm import Project
    from app.services.vocab_quiz import QuizAnswerGrade

    session = AsyncMock()
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    project = Project(
        id=project_id,
        user_id=user_id,
        title="General knowledge",
        kind="trivia",
        level="level3",
        target_language="en",
        daily_goal=10,
    )

    with (
        patch(
            "app.repositories.projects.get_by_id",
            new=AsyncMock(return_value=project),
        ),
        patch(
            "app.repositories.project_items.list_for_user",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.repositories.project_items.list_quiz_exclusion_contents",
            new=AsyncMock(return_value=[]),
        ),
    ):
        block = await projects_service.load_project_quiz_context(
            session,
            user_id,
            project_id,
            Settings(),
            quiz_grade=QuizAnswerGrade(
                is_correct=False,
                user_letter="D",
                correct_letter="A",
                word="Thirty Years' War",
                quiz_type="trivia",
                question="Which war ended with the Treaty of Westphalia in 1648?",
                attempt=3,
                tries_exhausted=True,
            ),
        )

    assert "FAILED" in block
    assert "DIFFERENT" in block
    assert "Do NOT redisplay" not in block
    assert "```vocab_quiz" in block or "vocab_quiz" in block


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
            "app.repositories.projects.get_by_id",
            new=AsyncMock(return_value=project),
        ),
        patch(
            "app.repositories.project_items.find_quiz_candidates",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.projects.quiz_grading.create_item",
            new=AsyncMock(),
        ) as create_mock,
        patch(
            "app.services.projects.quiz_grading.apply_quiz_result",
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
    assert grade.word == "Colossus"
    assert grade.quiz_type == "trivia"
    assert grade.question == "Which wonder stood at Rhodes?"
    create_mock.assert_awaited_once()
    apply_mock.assert_awaited_once()
    assert apply_mock.await_args.kwargs["is_correct"] is True
    assert create_mock.await_args.kwargs["definition"] == "Colossus"
    assert create_mock.await_args.kwargs["content"] == "Which wonder stood at Rhodes?"


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
            "app.repositories.projects.get_by_id",
            new=AsyncMock(return_value=project),
        ),
        patch(
            "app.repositories.project_items.find_quiz_candidates",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.projects.quiz_grading.create_item",
            new=AsyncMock(),
        ) as create_mock,
        patch(
            "app.services.projects.quiz_grading.apply_quiz_result",
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
            attempt=3,
        )

    assert grade is not None
    assert grade.is_correct is False
    assert grade.tries_exhausted is True
    assert grade.word == "Colossus"
    assert grade.quiz_type == "trivia"
    assert grade.question == "Which wonder stood at Rhodes?"
    create_mock.assert_awaited_once()
    apply_mock.assert_awaited_once()
    assert apply_mock.await_args.kwargs["is_correct"] is False
    assert create_mock.await_args.kwargs["definition"] == "Colossus"


@pytest.mark.asyncio
async def test_apply_deterministic_trivia_backfills_answer_on_existing_item():
    from unittest.mock import MagicMock

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
    existing = MagicMock()
    existing.project_id = project_id
    existing.list_title = "History"
    existing.content = "Which wonder stood at Rhodes?"
    existing.definition = None
    existing.status = "learning"
    existing.mastered = False

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
            "app.services.projects.quiz_grading.create_item",
            new=AsyncMock(),
        ) as create_mock,
        patch(
            "app.services.projects.quiz_grading.apply_quiz_result",
            new=AsyncMock(),
        ),
    ):
        grade = await projects_service.apply_deterministic_quiz_answer(
            session,
            user_id=user_id,
            chat_id=uuid.uuid4(),
            project_id=project_id,
            assistant_content=TRIVIA_FENCE,
            user_answer="A",
        )

    assert grade is not None
    assert grade.is_correct is True
    create_mock.assert_not_awaited()
    assert existing.definition == "Colossus"


@pytest.mark.asyncio
async def test_load_trivia_quiz_context_retries_question_not_topic():
    from app.core.config import Settings
    from app.models.orm import Project
    from app.services.vocab_quiz import QuizAnswerGrade

    session = AsyncMock()
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    project = Project(
        id=project_id,
        user_id=user_id,
        title="General knowledge",
        kind="trivia",
        level="level3",
        target_language="en",
        daily_goal=10,
    )

    with (
        patch(
            "app.repositories.projects.get_by_id",
            new=AsyncMock(return_value=project),
        ),
        patch(
            "app.repositories.project_items.list_for_user",
            new=AsyncMock(return_value=[]),
        ),
    ):
        block = await projects_service.load_project_quiz_context(
            session,
            user_id,
            project_id,
            Settings(),
            quiz_grade=QuizAnswerGrade(
                is_correct=False,
                user_letter="B",
                correct_letter="A",
                word="Treaty of Versailles",
                quiz_type="trivia",
                question="Which treaty officially ended World War I?",
            ),
        )

    assert "WRONG" in block
    assert "Which treaty officially ended World War I?" in block
    assert "Do NOT redisplay" in block
    assert "Never switch to vocabulary" in block
    assert "NEXT general-knowledge" not in block
    assert "as a fresh" not in block
    # Fence *example* omitted on wrong turns (the word vocab_quiz may still appear in the ban).
    assert "Colossus of Rhodes" not in block
    assert "What does it mean?" not in block
