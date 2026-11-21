from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import (
    ColumnElement,
    Integer,
    func,
    literal,
    null,
    or_,
    select,
    tuple_,
    union_all,
)
from sqlalchemy import cast as sql_cast
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.validation import devanagari_spellings
from app.models.orm import Attachment, Chat, Message
from app.modules.search.snippet import snippet
from app.repositories.keyset import decode_cursor, encode_cursor, page_of

# A title hit has no row of its own; this id sorts it after any other hit in the same chat.
_NO_ROW = UUID(int=0)
# Titles first, then the files sent in a chat, then messages; newest first within each.
_RANK = {"title": 2, "file": 1, "message": 0}


def _trgm_match(column: Any, query: str) -> ColumnElement[bool]:
    """pg_trgm `%` operator — uses GIN trigram indexes on title/content."""
    return cast(ColumnElement[bool], column.op("%")(query))


def _branch(
    match_type: str, row_id: Any, message_id: Any, created_at: Any, label: Any, role: Any
) -> list[Any]:
    """The columns every kind of hit carries, in one order for the union."""
    return [
        literal(match_type).label("match_type"),
        literal(_RANK[match_type], type_=Integer).label("rank"),
        row_id.label("row_id"),
        message_id.label("message_id"),
        created_at.label("created_at"),
        Chat.id.label("chat_id"),
        Chat.title.label("chat_title"),
        role.label("role"),
        label.label("label"),
        Chat.archived.label("archived"),
    ]


async def search_conversations(
    session: AsyncSession, user_id: UUID, query: str, limit: int = 20, cursor: str | None = None
) -> tuple[list[dict[str, Any]], str | None]:
    """Search chat titles, the names of files sent, and what was said, in that order.

    A message matches by its own words (``Message.search_text``: what the user typed, what
    Recall replied), never by an attachment marker or a file's extracted text: a 20-page
    PDF matched ordinary words, and "attachments" found every message with a file. A file
    matches by the name it was sent with and opens its message. Titles come first, then
    files, then messages, newest first within each; one row past the page is read instead
    of counting every hit.

    Message bodies match by substring through the user-scoped trigram index
    (``ix_messages_user_search_text_trgm``); the union carries the sort keys and small
    columns only, and the page's message words are read afterwards, by id, for snippets.
    """
    q = query.strip()
    if not q:
        return [], None

    # A dotted Devanagari letter is saved as one sign or as its letter and dot, whichever the
    # keyboard sent: each spelling is looked for. Any other query has one.
    spellings = devanagari_spellings(q)
    patterns = [f"%{_escaped(spelling)}%" for spelling in spellings]
    title_stmt = select(
        *_branch(
            "title",
            literal(_NO_ROW, type_=Message.id.type),
            sql_cast(null(), Message.id.type),
            func.coalesce(Chat.updated_at, Chat.created_at),
            Chat.title,
            literal("chat"),
        )
    ).where(
        Chat.user_id == user_id,
        Chat.title.isnot(None),
        Chat.title != "",
        or_(
            *(_trgm_match(Chat.title, spelling) for spelling in spellings),
            *(Chat.title.ilike(pattern, escape="\\") for pattern in patterns),
        ),
    )
    file_stmt = (
        select(
            *_branch(
                "file",
                Attachment.id,
                Message.id,
                Message.created_at,
                Attachment.original_filename,
                Message.role,
            )
        )
        .join(Message, Attachment.message_id == Message.id)
        .join(Chat, Message.chat_id == Chat.id)
        .where(
            Attachment.user_id == user_id,
            Chat.user_id == user_id,
            Attachment.source == "upload",
            or_(*(Attachment.original_filename.ilike(p, escape="\\") for p in patterns)),
        )
    )
    msg_stmt = (
        select(
            *_branch("message", Message.id, Message.id, Message.created_at, null(), Message.role)
        )
        .join(Chat, Message.chat_id == Chat.id)
        .where(
            Message.user_id == user_id,
            Chat.user_id == user_id,
            or_(*(Message.search_text.ilike(p, escape="\\") for p in patterns)),
        )
    )
    combined = union_all(title_stmt, file_stmt, msg_stmt).subquery("search_hits")
    order = (combined.c.rank, combined.c.created_at, combined.c.chat_id, combined.c.row_id)
    stmt = select(combined).order_by(*(column.desc() for column in order))
    if cursor is not None:
        at, (rank, chat_id, row_id) = decode_cursor(cursor, ids=3)
        values = (
            literal(rank.int, type_=Integer),
            literal(at, type_=combined.c.created_at.type),
            literal(chat_id, type_=combined.c.chat_id.type),
            literal(row_id, type_=combined.c.row_id.type),
        )
        stmt = stmt.where(tuple_(*order) < tuple_(*values))
    rows = (await session.execute(stmt.limit(limit + 1))).all()
    page, next_cursor = page_of(
        rows,
        limit,
        lambda row: encode_cursor(row.created_at, UUID(int=row.rank), row.chat_id, row.row_id),
    )

    words = await _message_words(session, user_id, page)
    return [_result(row, words, spellings) for row in page], next_cursor


def _escaped(query: str) -> str:
    return query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _result(row: Row[Any], words: dict[UUID, str], spellings: tuple[str, ...]) -> dict[str, Any]:
    if row.match_type == "message":
        text = words.get(row.row_id, "")
        folded = text.casefold()
        query = next((s for s in spellings if s.casefold() in folded), spellings[0])
        content = snippet(text, query, 120)
    elif row.match_type == "file":
        content = row.label or ""
    else:
        content = row.chat_title or ""
    return {
        "match_type": row.match_type,
        "message_id": row.message_id,
        "chat_id": row.chat_id,
        "chat_title": row.chat_title,
        "content": content,
        "role": row.role,
        "created_at": row.created_at or datetime.now(UTC),
        "archived": bool(row.archived),
    }


async def _message_words(
    session: AsyncSession, user_id: UUID, page: list[Row[Any]]
) -> dict[UUID, str]:
    """A page's message hits as their readers see them, by id (a deleted row reads empty).

    Read even for a page with none, so every search runs the same two statements whatever
    the page holds (a page of titles once skipped it: one statement for 50 chats, two for 5).
    """
    ids = [row.row_id for row in page if row.match_type == "message"]
    result = await session.execute(
        select(Message.id, Message.search_text).where(
            Message.user_id == user_id, Message.id.in_(ids)
        )
    )
    return {row.id: row.search_text or "" for row in result.all()}
