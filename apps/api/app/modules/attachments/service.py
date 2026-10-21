"""Public attachment operations for other product modules.

Other modules may import this file. They may not import the repository or
the extractor directly.
"""

from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable
from types import ModuleType
from typing import Any

from app.core.attachment_limits import MAX_ATTACHMENT_SIZE as MAX_ATTACHMENT_SIZE
from app.modules.attachments import jobs as _jobs
from app.modules.attachments import lifecycle as _lifecycle
from app.modules.attachments import rag as _rag
from app.modules.attachments import repository as attachments_repo
from app.modules.attachments.content_types import bytes_match_claimed as bytes_match_claimed
from app.modules.attachments.content_types import is_image_content_type as is_image_content_type
from app.modules.attachments.content_types import (
    normalize_content_type as normalize_content_type,
)


def _call_through(module: ModuleType, name: str) -> Callable[..., Awaitable[Any]]:
    """Look ``module.name`` up on every call, so a patch on the owning file applies."""
    target = getattr(module, name)

    @functools.wraps(target)
    async def call(*args: Any, **kwargs: Any) -> Any:
        return await getattr(module, name)(*args, **kwargs)

    return call


create_pending = _call_through(attachments_repo, "create_pending")
enqueue_index_jobs = _call_through(_jobs, "enqueue_index_jobs")
get_by_id = _call_through(attachments_repo, "get_by_id")
get_by_ids = _call_through(attachments_repo, "get_by_ids")
chat_has_document_chunks = _call_through(_rag, "chat_has_document_chunks")
hide_from_gallery = _call_through(attachments_repo, "hide_from_gallery")
insert_verified_clone = _call_through(attachments_repo, "insert_verified_clone")
link_to_message = _call_through(attachments_repo, "link_to_message")
list_for_message_ids = _call_through(attachments_repo, "list_for_message_ids")
list_for_user = _call_through(attachments_repo, "list_for_user")
mark_verified = _call_through(attachments_repo, "mark_verified")
mark_verified_many = _call_through(attachments_repo, "mark_verified_many")
purge_attachments_for_user = _call_through(_lifecycle, "purge_attachments_for_user")
