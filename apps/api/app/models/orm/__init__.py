"""SQLAlchemy mapped models. Prefer `from app.models.orm import User`.

Schedule exports `TodoItem`. Database table and column names are unchanged.
"""

from app.models.orm.attachments import MessageChunk
from app.models.orm.chat import Chat, Message
from app.models.orm.integrations import PushToken
from app.models.orm.usage import ProductEvent, UsageDaily
from app.models.orm.user import User
from app.modules.attachments.models import Attachment, AttachmentChunk
from app.modules.integrations.models import (
    SuggestedReminder,
    UserCalendarConnection,
    UserGmailConnection,
)
from app.modules.job_search.models import JobMatch, JobSearchProfile
from app.modules.memory.models import Memory, MemoryArea
from app.modules.suggestions.models import Suggestion
from app.modules.todos.models import TodoItem

__all__ = [
    "Attachment",
    "AttachmentChunk",
    "Chat",
    "JobMatch",
    "JobSearchProfile",
    "Memory",
    "MemoryArea",
    "Message",
    "MessageChunk",
    "ProductEvent",
    "PushToken",
    "SuggestedReminder",
    "Suggestion",
    "TodoItem",
    "UsageDaily",
    "User",
    "UserCalendarConnection",
    "UserGmailConnection",
]
