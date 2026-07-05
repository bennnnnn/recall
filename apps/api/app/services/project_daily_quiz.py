"""Pre-generated daily quiz batches — vocab (multi-modality) and trivia (MCQ only)."""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.gateways import litellm_gateway
from app.gateways.mock_llm import should_mock_llm
from app.models.orm import Project, ProjectItem, ProjectQuizQuestion
from app.models.schemas import (
    ProjectDailyQuizOut,
    ProjectQuizAnswerResultOut,
    ProjectQuizQuestionOut,
    QuizChoiceOut,
    QuizModality,
)
from app.repositories import project_items as project_items_repo
from app.repositories import project_quiz_questions as quiz_questions_repo
from app.repositories import projects as projects_repo
from app.services import daily_learning
from app.services.projects import (
    _LEVEL_LABELS,
    DEFAULT_LIST,
    _find_item,
    _find_item_by_content,
    _is_language_project,
    _is_trivia_project,
    _item_status,
    _level_guidance,
    _normalize,
)

logger = logging.getLogger(__name__)

VOCAB_MODALITIES: list[Literal["mcq", "definition", "sentence"]] = [
    "mcq",
    "definition",
    "sentence",
]
TRIVIA_MODALITIES: list[Literal["mcq"]] = ["mcq"]


class _QuizChoice(BaseModel):
    letter: Literal["A", "B", "C", "D"]
    text: str = Field(min_length=1, max_length=500)


class _NewVocabWord(BaseModel):
    content: str = Field(min_length=1, max_length=80)
    part_of_speech: str = Field(min_length=1, max_length=30)
    definition: str = Field(min_length=1, max_length=500)
    example_sentence: str = Field(min_length=1, max_length=500)


class _NewVocabWords(BaseModel):
    words: list[_NewVocabWord] = Field(min_length=1, max_length=20)


class _GeneratedQuestion(BaseModel):
    topic: str = Field(min_length=1, max_length=200)
    part_of_speech: str | None = Field(default=None, max_length=30)
    question: str = Field(min_length=1, max_length=1000)
    choices: list[_QuizChoice] = Field(min_length=2, max_length=4)
    correct: Literal["A", "B", "C", "D"]
    reference_definition: str | None = Field(default=None, max_length=2000)


class _GeneratedBatch(BaseModel):
    questions: list[_GeneratedQuestion] = Field(min_length=1, max_length=20)


class _GradeResult(BaseModel):
    is_correct: bool
    feedback: str = Field(min_length=1, max_length=4000)
    allow_retry: bool = False


class _MarkdownFeedback(BaseModel):
    feedback: str = Field(min_length=1, max_length=4000)


def _local_today(timezone_name: str) -> date:
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = ZoneInfo("UTC")
    return datetime.now(tz).date()


def _question_out(row: ProjectQuizQuestion) -> ProjectQuizQuestionOut:
    choices = [
        QuizChoiceOut.model_validate(c)
        for c in row.choices
        if isinstance(c, dict) and c.get("letter") and c.get("text")
    ]
    modalities: list[QuizModality] = (
        list(VOCAB_MODALITIES) if row.quiz_kind == "vocab" else list(TRIVIA_MODALITIES)
    )
    return ProjectQuizQuestionOut(
        id=row.id,
        sequence=row.sequence,
        quiz_kind=row.quiz_kind,  # type: ignore[arg-type]
        topic=row.topic,
        part_of_speech=row.part_of_speech,
        question_text=row.question_text,
        choices=choices,
        status=row.status,  # type: ignore[arg-type]
        allowed_modalities=modalities,
    )


async def get_daily_quiz(
    session: AsyncSession,
    *,
    user_id: UUID,
    project_id: UUID,
    timezone_name: str,
) -> ProjectDailyQuizOut | None:
    project = await projects_repo.get_by_id(session, project_id, user_id)
    if project is None or not (_is_language_project(project) or _is_trivia_project(project)):
        return None

    quiz_date = _local_today(timezone_name)
    daily_goal = daily_learning.resolve_daily_goal(project)
    answered = await quiz_questions_repo.count_answered_today(session, project_id, quiz_date)
    current_row = await quiz_questions_repo.next_pending(session, project_id, quiz_date)
    complete = answered >= daily_goal or (current_row is None and answered > 0)
    return ProjectDailyQuizOut(
        quiz_date=quiz_date,
        daily_goal=daily_goal,
        answered_count=answered,
        complete=complete,
        current=_question_out(current_row) if current_row else None,
    )


async def ensure_daily_quiz(
    session: AsyncSession,
    settings: Settings,
    *,
    user_id: UUID,
    project_id: UUID,
    timezone_name: str,
) -> ProjectDailyQuizOut | None:
    project = await projects_repo.get_by_id(session, project_id, user_id)
    if project is None or not (_is_language_project(project) or _is_trivia_project(project)):
        return None

    quiz_date = _local_today(timezone_name)
    daily_goal = daily_learning.resolve_daily_goal(project)
    if not await quiz_questions_repo.batch_exists(
        session, project_id, quiz_date, min_count=daily_goal
    ):
        await _generate_batch(
            session,
            settings,
            user_id=user_id,
            project=project,
            quiz_date=quiz_date,
            count=daily_goal,
        )
        await session.commit()

    return await get_daily_quiz(
        session,
        user_id=user_id,
        project_id=project_id,
        timezone_name=timezone_name,
    )


async def submit_answer(
    session: AsyncSession,
    settings: Settings,
    *,
    user_id: UUID,
    project_id: UUID,
    question_id: UUID,
    modality: Literal["mcq", "definition", "sentence"],
    letter: str | None,
    text: str | None,
    timezone_name: str,
    chat_id: UUID | None = None,
    skip: bool = False,
) -> ProjectQuizAnswerResultOut | None:
    project = await projects_repo.get_by_id(session, project_id, user_id)
    if project is None:
        return None

    question = await quiz_questions_repo.get_by_id(
        session, question_id, user_id=user_id, project_id=project_id
    )
    if question is None or question.status != "pending":
        return None

    if skip:
        correct_text = next(
            (
                c.get("text", "")
                for c in question.choices
                if c.get("letter") == question.correct_letter
            ),
            "",
        )
        feedback = (
            f"Skipped. The answer is **{question.correct_letter}**"
            + (f" — {correct_text}" if correct_text else "")
            + "."
        )
        if question.reference_definition:
            feedback += f"\n\n*{question.topic}*: {question.reference_definition}"
        await quiz_questions_repo.mark_answered(
            session,
            question,
            modality="skip",
            is_correct=False,
            letter=None,
            text=None,
        )
        quiz_date = question.quiz_date
        daily_goal = daily_learning.resolve_daily_goal(project)
        answered = await quiz_questions_repo.count_answered_today(session, project_id, quiz_date)
        batch_complete = answered >= daily_goal
        next_row = await quiz_questions_repo.next_pending(session, project_id, quiz_date)
        if batch_complete:
            _tomorrow_task = asyncio.create_task(
                _generate_tomorrow_batch(
                    settings,
                    user_id=user_id,
                    project_id=project_id,
                    timezone_name=timezone_name,
                )
            )
            del _tomorrow_task
        return ProjectQuizAnswerResultOut(
            is_correct=False,
            feedback=feedback,
            mastered=False,
            batch_complete=batch_complete,
            allow_retry=False,
            suggest_mcq=False,
            next_question=_question_out(next_row) if next_row else None,
        )

    is_trivia = question.quiz_kind == "trivia"
    if is_trivia and modality != "mcq":
        return None
    if modality == "mcq" and not letter:
        return None
    if modality in ("definition", "sentence") and not (text or "").strip():
        return None

    is_correct = False
    allow_retry = False
    feedback = ""
    mastered = False

    if modality == "mcq":
        is_correct = letter is not None and letter.upper() == question.correct_letter.upper()
        feedback = await _explain_mcq(settings, question, letter or "", is_correct)
    else:
        grade = await _grade_free_text(settings, question, modality, text or "")
        if grade is None:
            feedback = (
                "I couldn't grade that answer right now. Try again or switch to multiple choice."
            )
            allow_retry = True
            return ProjectQuizAnswerResultOut(
                is_correct=False,
                feedback=feedback,
                mastered=False,
                batch_complete=False,
                allow_retry=True,
                suggest_mcq=False,
                next_question=_question_out(question),
            )
        is_correct = grade.is_correct
        feedback = grade.feedback
        allow_retry = grade.allow_retry and not is_correct

    if is_correct or not allow_retry:
        await quiz_questions_repo.mark_answered(
            session,
            question,
            modality=modality,
            is_correct=is_correct,
            letter=letter,
            text=text,
        )
        mastered = False
        if is_correct:
            mastered = await _apply_mastery(
                session,
                user_id=user_id,
                project=project,
                question=question,
                chat_id=chat_id,
            )

    quiz_date = question.quiz_date
    daily_goal = daily_learning.resolve_daily_goal(project)
    answered = await quiz_questions_repo.count_answered_today(session, project_id, quiz_date)
    batch_complete = answered >= daily_goal
    next_row = await quiz_questions_repo.next_pending(session, project_id, quiz_date)

    if batch_complete:
        _tomorrow_task = asyncio.create_task(
            _generate_tomorrow_batch(
                settings,
                user_id=user_id,
                project_id=project_id,
                timezone_name=timezone_name,
            )
        )
        del _tomorrow_task

    if is_correct or not allow_retry:
        return ProjectQuizAnswerResultOut(
            is_correct=is_correct,
            feedback=feedback,
            mastered=mastered if is_correct else False,
            batch_complete=batch_complete,
            allow_retry=False,
            suggest_mcq=False,
            next_question=_question_out(next_row) if next_row else None,
        )

    return ProjectQuizAnswerResultOut(
        is_correct=False,
        feedback=feedback,
        mastered=False,
        batch_complete=False,
        allow_retry=True,
        suggest_mcq=True,
        next_question=_question_out(question),
    )


async def _apply_mastery(
    session: AsyncSession,
    *,
    user_id: UUID,
    project: Project,
    question: ProjectQuizQuestion,
    chat_id: UUID | None,
) -> bool:
    items = await project_items_repo.list_for_user(
        session, user_id, project_id=project.id, limit=500
    )
    if _is_trivia_project(project):
        topic = question.topic.strip()
        qtext = question.question_text.strip()
        list_title = topic or DEFAULT_LIST
        status = "mastered"
        existing = _find_item(items, project.id, list_title, qtext)
        if existing:
            if _item_status(existing) != status:
                await project_items_repo.update(session, existing, status=status)
        else:
            await project_items_repo.create(
                session,
                user_id=user_id,
                project_id=project.id,
                content=qtext,
                list_title=list_title,
                chat_id=chat_id,
                status=status,
            )
        return True

    if not _is_language_project(project):
        return False

    word = question.topic.strip()
    if not word:
        return False
    pos = (question.part_of_speech or "other").strip().lower()
    from app.repositories.project_items import pos_list_title

    list_title = pos_list_title(pos)
    existing = (
        _find_item(items, project.id, list_title, word)
        if question.project_item_id is None
        else next((i for i in items if i.id == question.project_item_id), None)
    ) or _find_item_by_content(items, project.id, word)
    if existing:
        if _item_status(existing) != "mastered":
            await project_items_repo.update(session, existing, status="mastered")
    else:
        await project_items_repo.create(
            session,
            user_id=user_id,
            project_id=project.id,
            content=word,
            list_title=list_title,
            part_of_speech=pos,
            definition=question.reference_definition,
            chat_id=chat_id,
            status="mastered",
        )
    return True


async def _generate_batch(
    session: AsyncSession,
    settings: Settings,
    *,
    user_id: UUID,
    project: Project,
    quiz_date: date,
    count: int,
) -> None:
    if _is_language_project(project):
        await _generate_vocab_batch(
            session, settings, user_id=user_id, project=project, quiz_date=quiz_date, count=count
        )
    elif _is_trivia_project(project):
        await _generate_trivia_batch(
            session, settings, user_id=user_id, project=project, quiz_date=quiz_date, count=count
        )


def _mock_new_vocab_words(
    count: int,
    *,
    existing: set[str],
    start_n: int = 1,
) -> list[_NewVocabWord]:
    out: list[_NewVocabWord] = []
    n = start_n
    while len(out) < count:
        word = f"word{n}"
        n += 1
        if _normalize(word) in existing:
            continue
        out.append(
            _NewVocabWord(
                content=word,
                part_of_speech="noun",
                definition=f"The meaning of {word}",
                example_sentence=f"I learned the word {word} today.",
            )
        )
        existing.add(_normalize(word))
    return out


async def _llm_new_vocab_words(
    settings: Settings,
    project: Project,
    *,
    count: int,
    existing_terms: list[str],
) -> _NewVocabWords | None:
    if count <= 0:
        return None
    level = _LEVEL_LABELS.get(project.level or "level1", "Beginner")
    known = "\n".join(f"- {t}" for t in existing_terms[:80]) or "(none yet)"
    prompt = (
        f'Generate exactly {count} NEW English vocabulary words for project "{project.title}".\n'
        f"Level: {level}. {_level_guidance(project.level or 'level1')}\n"
        f"Do NOT duplicate any of these existing terms:\n{known}\n\n"
        'Return JSON: {"words": [{"content": "...", "part_of_speech": "noun", '
        '"definition": "...", "example_sentence": "..."}]}. '
        "Each word needs part_of_speech (noun/verb/adjective/etc.)."
    )
    return await litellm_gateway.complete_structured(
        settings=settings,
        model_alias="memory-model",
        messages=[
            {"role": "system", "content": "You generate vocabulary word lists as JSON only."},
            {"role": "user", "content": prompt},
        ],
        schema=_NewVocabWords,
        max_tokens=1024,
    )


async def _provision_new_vocab_words(
    session: AsyncSession,
    settings: Settings,
    *,
    user_id: UUID,
    project: Project,
    items: list[ProjectItem],
    pool: list[ProjectItem],
    count: int,
) -> list[ProjectItem]:
    """Add fresh project_items when the new/learning pool is too small for today's batch."""
    if count <= 0:
        return items

    from app.models.orm import ProjectItem as ProjectItemOrm
    from app.repositories.project_items import pos_list_title

    existing_norm = {_normalize(i.content) for i in items}
    existing_terms = [i.content.strip() for i in items if i.content.strip()]

    if should_mock_llm(settings):
        new_words = _mock_new_vocab_words(count, existing=set(existing_norm))
    else:
        batch = await _llm_new_vocab_words(
            settings, project, count=count, existing_terms=existing_terms
        )
        new_words = batch.words if batch else []

    if not new_words and should_mock_llm(settings):
        new_words = _mock_new_vocab_words(count, existing=set(existing_norm))

    for word in new_words:
        norm = _normalize(word.content)
        if norm in existing_norm:
            continue
        pos = word.part_of_speech.strip().lower()
        item = ProjectItemOrm(
            user_id=user_id,
            project_id=project.id,
            content=word.content.strip(),
            list_title=pos_list_title(pos),
            definition=word.definition.strip(),
            example_sentence=word.example_sentence.strip(),
            part_of_speech=pos,
            status="new",
            mastered=False,
        )
        session.add(item)
        await session.flush()
        items.append(item)
        pool.append(item)
        existing_norm.add(norm)

    return items


async def _generate_vocab_batch(
    session: AsyncSession,
    settings: Settings,
    *,
    user_id: UUID,
    project: Project,
    quiz_date: date,
    count: int,
) -> None:
    existing_topics = await quiz_questions_repo.list_quizzed_topics(session, project.id)
    items = await project_items_repo.list_for_user(
        session, user_id, project_id=project.id, limit=500
    )
    pool = [
        i
        for i in items
        if _item_status(i) in ("new", "learning") and _normalize(i.content) not in existing_topics
    ]
    already = await quiz_questions_repo.list_for_project_date(session, project.id, quiz_date)
    start_seq = len(already)
    need_questions = count - start_seq
    if need_questions <= 0:
        return

    pool_shortfall = need_questions - len(pool)
    if pool_shortfall > 0:
        items = await _provision_new_vocab_words(
            session,
            settings,
            user_id=user_id,
            project=project,
            items=items,
            pool=pool,
            count=pool_shortfall,
        )

    generated: list[_GeneratedQuestion] = []
    if should_mock_llm(settings):
        generated = _mock_vocab_questions(pool, need_questions)
    else:
        batch = await _llm_generate_vocab(settings, project, pool, need_questions)
        if batch:
            generated = batch.questions

    seq = start_seq
    for q in generated:
        if seq >= count:
            break
        topic_norm = quiz_questions_repo.normalize_topic(q.topic)
        if topic_norm in existing_topics:
            continue
        item = _find_item_by_content(items, project.id, q.topic)
        choices = [{"letter": c.letter, "text": c.text} for c in q.choices]
        row = await quiz_questions_repo.insert_question(
            session,
            user_id=user_id,
            project_id=project.id,
            project_item_id=item.id if item else None,
            quiz_date=quiz_date,
            sequence=seq,
            quiz_kind="vocab",
            topic=q.topic,
            part_of_speech=q.part_of_speech,
            question_text=q.question,
            choices=choices,
            correct_letter=q.correct,
            reference_definition=q.reference_definition,
        )
        if row is not None:
            existing_topics.add(topic_norm)
            seq += 1


async def _generate_trivia_batch(
    session: AsyncSession,
    settings: Settings,
    *,
    user_id: UUID,
    project: Project,
    quiz_date: date,
    count: int,
) -> None:
    existing_topics = await quiz_questions_repo.list_quizzed_topics(session, project.id)
    already = await quiz_questions_repo.list_for_project_date(session, project.id, quiz_date)
    start_seq = len(already)
    need = count - start_seq
    if need <= 0:
        return

    generated: list[_GeneratedQuestion] = []
    if should_mock_llm(settings):
        generated = _mock_trivia_questions(project, need)
    else:
        batch = await _llm_generate_trivia(settings, project, need)
        if batch:
            generated = batch.questions

    seq = start_seq
    for q in generated:
        if seq >= count:
            break
        topic_norm = quiz_questions_repo.normalize_topic(q.topic)
        if topic_norm in existing_topics:
            continue
        choices = [{"letter": c.letter, "text": c.text} for c in q.choices]
        row = await quiz_questions_repo.insert_question(
            session,
            user_id=user_id,
            project_id=project.id,
            project_item_id=None,
            quiz_date=quiz_date,
            sequence=seq,
            quiz_kind="trivia",
            topic=q.topic,
            part_of_speech=None,
            question_text=q.question,
            choices=choices,
            correct_letter=q.correct,
            reference_definition=None,
        )
        if row is not None:
            existing_topics.add(topic_norm)
            seq += 1


def _mock_vocab_questions(pool: list[ProjectItem], count: int) -> list[_GeneratedQuestion]:
    out: list[_GeneratedQuestion] = []
    for item in pool[:count]:
        word = item.content.strip()
        definition = (item.definition or "a common English word").strip()
        out.append(
            _GeneratedQuestion(
                topic=word,
                part_of_speech=item.part_of_speech,
                question=f'What does "{word}" mean?',
                choices=[
                    _QuizChoice(letter="A", text="A completely wrong meaning"),
                    _QuizChoice(letter="B", text=definition[:120]),
                    _QuizChoice(letter="C", text="An unrelated definition"),
                    _QuizChoice(letter="D", text="Another incorrect option"),
                ],
                correct="B",
                reference_definition=definition,
            )
        )
    while len(out) < count:
        n = len(out) + 1
        word = f"word{n}"
        out.append(
            _GeneratedQuestion(
                topic=word,
                part_of_speech="noun",
                question=f'What does "{word}" mean?',
                choices=[
                    _QuizChoice(letter="A", text="Wrong A"),
                    _QuizChoice(letter="B", text="Correct meaning"),
                    _QuizChoice(letter="C", text="Wrong C"),
                    _QuizChoice(letter="D", text="Wrong D"),
                ],
                correct="B",
                reference_definition="Correct meaning",
            )
        )
    return out[:count]


def _mock_trivia_questions(project: Project, count: int) -> list[_GeneratedQuestion]:
    topics = (project.description or "General knowledge").split(",")
    out: list[_GeneratedQuestion] = []
    for i in range(count):
        topic = topics[i % len(topics)].strip() or "Science"
        out.append(
            _GeneratedQuestion(
                topic=topic,
                question=f"Sample {topic} question #{i + 1}?",
                choices=[
                    _QuizChoice(letter="A", text="Wrong answer"),
                    _QuizChoice(letter="B", text="Correct answer"),
                    _QuizChoice(letter="C", text="Another wrong"),
                    _QuizChoice(letter="D", text="Also wrong"),
                ],
                correct="B",
            )
        )
    return out


async def _llm_generate_vocab(
    settings: Settings,
    project: Project,
    pool: list[ProjectItem],
    count: int,
) -> _GeneratedBatch | None:
    if count <= 0:
        return None
    level = _LEVEL_LABELS.get(project.level or "level1", "Beginner")
    words = [f"{i.content} [{i.part_of_speech or 'other'}]" for i in pool[:40]]
    word_block = (
        "\n".join(f"- {w}" for w in words) if words else "(generate new level-appropriate words)"
    )
    prompt = (
        f"Generate exactly {count} multiple-choice vocabulary quiz questions "
        f'for project "{project.title}".\n'
        f"English level: {level}. {_level_guidance(project.level or 'level1')}\n"
        f"Prefer these new/learning words (do not repeat words already quizzed):\n{word_block}\n\n"
        'Return JSON: {"questions": [{"topic": "word", "part_of_speech": "noun", '
        '"question": "What does ... mean?", "choices": [{"letter":"A","text":"..."}, ...], '
        '"correct": "B", "reference_definition": "..."}]}. '
        "Each question needs exactly 4 choices A-D and one correct letter."
    )
    return await litellm_gateway.complete_structured(
        settings=settings,
        model_alias="memory-model",
        messages=[
            {"role": "system", "content": "You generate vocabulary quiz JSON only."},
            {"role": "user", "content": prompt},
        ],
        schema=_GeneratedBatch,
        max_tokens=2048,
    )


async def _llm_generate_trivia(
    settings: Settings,
    project: Project,
    count: int,
) -> _GeneratedBatch | None:
    if count <= 0:
        return None
    topics = project.description or "general knowledge"
    prompt = (
        f"Generate exactly {count} trivia multiple-choice questions for topics: {topics}.\n"
        'Return JSON: {"questions": [{"topic": "History", "question": "...?", '
        '"choices": [{"letter":"A","text":"..."}, ...], "correct": "B"}]}. '
        "topic = category label only. Exactly 4 choices per question.\n"
        "Only use well-established facts you are confident are correct — the kind found "
        "in encyclopedias or textbooks. Avoid obscure trivia, disputed claims, statistics "
        "that change over time (e.g. current records, populations, rankings), and anything "
        "from after your training cutoff. If you are not sure a fact is accurate, pick a "
        "different, more certain question instead."
    )
    return await litellm_gateway.complete_structured(
        settings=settings,
        model_alias="memory-model",
        messages=[
            {
                "role": "system",
                "content": (
                    "You generate trivia quiz JSON only. Every question and its correct "
                    "answer must be a well-established, verifiable fact — never guess or "
                    "invent one."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        schema=_GeneratedBatch,
        max_tokens=2048,
    )


async def _explain_mcq(
    settings: Settings,
    question: ProjectQuizQuestion,
    letter: str,
    is_correct: bool,
) -> str:
    if should_mock_llm(settings):
        if is_correct:
            return (
                f"**{letter}** is correct! *{question.topic}* - well done.\n\n"
                "Want to try another format next time, or keep going?"
            )
        correct = question.correct_letter
        return (
            f"Not quite — the answer is **{correct}**. "
            f"*{question.topic}*: {question.reference_definition or question.question_text}\n\n"
            "You can retry with a definition or sentence, or move on."
        )

    correct_text = next(
        (c.get("text", "") for c in question.choices if c.get("letter") == question.correct_letter),
        "",
    )
    prompt = (
        f"Vocabulary/trivia quiz feedback.\n"
        f"Word/topic: {question.topic}\n"
        f"Question: {question.question_text}\n"
        f"User picked: {letter}\n"
        f"Correct: {question.correct_letter} ({correct_text})\n"
        f"Reference: {question.reference_definition or ''}\n"
        f"User was {'correct' if is_correct else 'incorrect'}.\n"
        "Write 2-4 sentences: encouraging, explain briefly, one example if vocab. Markdown only."
    )
    text = await litellm_gateway.complete_structured(
        settings=settings,
        model_alias="free-chat",
        messages=[{"role": "user", "content": prompt}],
        schema=_MarkdownFeedback,
        max_tokens=256,
    )
    return (
        text.feedback.strip()
        if text
        else ("Correct!" if is_correct else "Not quite — try again or switch format.")
    )


async def _grade_free_text(
    settings: Settings,
    question: ProjectQuizQuestion,
    modality: Literal["definition", "sentence"],
    answer: str,
) -> _GradeResult | None:
    if should_mock_llm(settings):
        ref = (question.reference_definition or "").casefold()
        ok = bool(ref and ref in answer.casefold())
        if modality == "sentence":
            ok = question.topic.casefold() in answer.casefold() and len(answer.split()) >= 4
        return _GradeResult(
            is_correct=ok,
            feedback=(
                "Great job!"
                if ok
                else "Not quite — here's a hint: "
                f"{question.reference_definition or question.topic}. Try again, pick A-D, or skip."
            ),
            allow_retry=not ok,
        )

    task = "definition" if modality == "definition" else "example sentence using the word"
    prompt = (
        f"Grade this English learner's {task}.\n"
        f"Word: {question.topic}\n"
        f"Reference definition: {question.reference_definition or 'unknown'}\n"
        f"Student answer: {answer.strip()}\n\n"
        'Return JSON: {"is_correct": bool, "feedback": "markdown feedback", "allow_retry": bool}. '
        "If wrong, suggest improvement and set allow_retry true unless answer is nonsense."
    )
    return await litellm_gateway.complete_structured(
        settings=settings,
        model_alias="memory-model",
        messages=[{"role": "user", "content": prompt}],
        schema=_GradeResult,
        max_tokens=512,
    )


async def _generate_tomorrow_batch(
    settings: Settings,
    *,
    user_id: UUID,
    project_id: UUID,
    timezone_name: str,
) -> None:
    from app.core.db import SessionLocal

    try:
        async with SessionLocal() as session:
            project = await projects_repo.get_by_id(session, project_id, user_id)
            if project is None:
                return
            tomorrow = _local_today(timezone_name) + timedelta(days=1)
            daily_goal = daily_learning.resolve_daily_goal(project)
            if await quiz_questions_repo.batch_exists(
                session, project_id, tomorrow, min_count=daily_goal
            ):
                return
            await _generate_batch(
                session,
                settings,
                user_id=user_id,
                project=project,
                quiz_date=tomorrow,
                count=daily_goal,
            )
            await session.commit()
    except Exception:
        logger.exception("Tomorrow quiz batch failed project_id=%s", project_id)
