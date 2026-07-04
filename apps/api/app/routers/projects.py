from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.orm import User
from app.models.schemas import (
    ProjectCreate,
    ProjectDeckItemCreate,
    ProjectDeckSummary,
    ProjectDetailOut,
    ProjectItemOut,
    ProjectItemUpdate,
    ProjectOut,
    ProjectPosGroupSummary,
    ProjectQuizAnswerIn,
    ProjectStats,
    ProjectUpdate,
)
from app.repositories import project_items as project_items_repo
from app.repositories import projects as projects_repo
from app.services import home as home_service
from app.services import projects as projects_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[ProjectOut]:
    items = await projects_repo.list_for_user(session, user.id)
    return [ProjectOut.model_validate(item) for item in items if item.kind != "programming"]


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ProjectOut:
    kind = body.kind
    if kind == "vocabulary":
        kind = "language"
    if kind == "programming":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="programming_not_supported",
        )
    if kind == "language":
        existing = await projects_repo.find_language_by_target(
            session, user.id, body.target_language
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="language_project_exists",
            )
    if kind == "trivia":
        existing = await projects_repo.find_trivia_project(session, user.id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="trivia_project_exists",
            )
    item = await projects_repo.create(
        session,
        user_id=user.id,
        title=body.title,
        description=body.description,
        kind=kind,
        target_language=body.target_language,
        native_language=body.native_language,
        level=body.level,
        daily_goal=body.daily_goal if kind in ("language", "trivia") else None,
    )
    await home_service.invalidate_home_cache(user.id)
    return ProjectOut.model_validate(item)


@router.get("/{project_id}", response_model=ProjectDetailOut)
async def get_project(
    project_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ProjectDetailOut:
    item = await projects_repo.get_by_id(session, project_id, user.id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if item.kind == "programming":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    is_language = item.kind in ("language", "vocabulary")
    if is_language:
        await project_items_repo.normalize_pos_list_titles(session, user.id, project_id)
        stats_raw = await project_items_repo.count_stats(
            session, project_id, user.id, timezone_name=user.timezone or "UTC"
        )
        stats = ProjectStats.model_validate(stats_raw)
        summaries = await project_items_repo.pos_group_summaries(session, user.id, project_id)
        pos_groups = [ProjectPosGroupSummary.model_validate(s) for s in summaries]
        deck_rows = await project_items_repo.deck_summaries(session, user.id, project_id)
        decks = [ProjectDeckSummary.model_validate(d) for d in deck_rows]
        return ProjectDetailOut(
            **ProjectOut.model_validate(item).model_dump(),
            mastered_count=stats.mastered_count,
            total_count=stats.total,
            stats=stats,
            lists=[],
            by_part_of_speech=[],
            pos_groups=pos_groups,
            decks=decks,
        )

    if item.kind == "trivia":
        project_items = await project_items_repo.list_for_user(
            session, user.id, project_id=project_id
        )
        stats_raw = await project_items_repo.count_stats(
            session, project_id, user.id, timezone_name=user.timezone or "UTC"
        )
        stats = ProjectStats.model_validate(stats_raw)
        lists = projects_service.group_trivia_items(project_items)
        return ProjectDetailOut(
            **ProjectOut.model_validate(item).model_dump(),
            mastered_count=stats.mastered_count,
            total_count=stats.total,
            stats=stats,
            lists=lists,
            by_part_of_speech=[],
            pos_groups=[],
            decks=[],
        )

    project_items = await project_items_repo.list_for_user(session, user.id, project_id=project_id)
    stats = projects_service.build_stats(project_items)
    lists = projects_service.group_items(project_items)
    return ProjectDetailOut(
        **ProjectOut.model_validate(item).model_dump(),
        mastered_count=stats.mastered_count,
        total_count=stats.total,
        stats=stats,
        lists=lists,
        by_part_of_speech=projects_service.group_by_part_of_speech(project_items),
        pos_groups=[],
        decks=[],
    )


@router.get("/{project_id}/decks", response_model=list[ProjectDeckSummary])
async def list_project_decks(
    project_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[ProjectDeckSummary]:
    project = await projects_repo.get_by_id(session, project_id, user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    rows = await project_items_repo.deck_summaries(session, user.id, project_id)
    return [ProjectDeckSummary.model_validate(r) for r in rows]


@router.post(
    "/{project_id}/decks/{deck_title}/items",
    response_model=ProjectItemOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_deck_item(
    project_id: UUID,
    deck_title: str,
    body: ProjectDeckItemCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ProjectItemOut:
    project = await projects_repo.get_by_id(session, project_id, user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if project.kind not in ("language", "vocabulary"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Not a language project"
        )
    item = await project_items_repo.create_deck_item(
        session,
        user_id=user.id,
        project_id=project_id,
        deck_title=deck_title,
        content=body.content,
        definition=body.definition,
        example_sentence=body.example_sentence,
    )
    await home_service.invalidate_home_cache(user.id)
    return ProjectItemOut.model_validate(item)


@router.get("/{project_id}/pos/{part_of_speech}/items", response_model=list[ProjectItemOut])
async def list_pos_items(
    project_id: UUID,
    part_of_speech: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
) -> list[ProjectItemOut]:
    project = await projects_repo.get_by_id(session, project_id, user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if project.kind not in ("language", "vocabulary"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Not a language project"
        )
    items = await project_items_repo.list_by_pos(
        session,
        user.id,
        project_id,
        part_of_speech,
        limit=min(limit, 100),
        offset=max(offset, 0),
    )
    return [ProjectItemOut.model_validate(i) for i in items]


@router.patch("/{project_id}/items/{item_id}", response_model=ProjectItemOut)
async def update_project_item(
    project_id: UUID,
    item_id: UUID,
    body: ProjectItemUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ProjectItemOut:
    project = await projects_repo.get_by_id(session, project_id, user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    item = await project_items_repo.get_by_id(session, item_id, user.id, project_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    updated = await project_items_repo.update(session, item, **patch)
    await home_service.invalidate_home_cache(user.id)
    return ProjectItemOut.model_validate(updated)


@router.post("/{project_id}/quiz-answer", status_code=status.HTTP_204_NO_CONTENT)
async def record_project_quiz_answer(
    project_id: UUID,
    body: ProjectQuizAnswerIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    recorded = await projects_service.record_project_quiz_answer(
        session,
        user_id=user.id,
        project_id=project_id,
        chat_id=body.chat_id,
        assistant_message_id=body.assistant_message_id,
        letter=body.letter,
        topic=body.topic,
        question=body.question,
        is_correct=body.is_correct,
    )
    if not recorded:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="quiz_answer_not_recorded",
        )


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: UUID,
    body: ProjectUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ProjectOut:
    item = await projects_repo.get_by_id(session, project_id, user.id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    patch = body.model_dump(exclude_unset=True)
    if patch.get("kind") == "vocabulary":
        patch["kind"] = "language"
    updated = await projects_repo.update(session, item, **patch)
    await home_service.invalidate_home_cache(user.id)
    return ProjectOut.model_validate(updated)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    deleted = await projects_repo.delete_by_id(session, project_id, user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    await home_service.invalidate_home_cache(user.id)
