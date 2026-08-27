"""SQLAlchemy mapped models. Prefer `from app.models.orm import User`.

Canonical product names: Learning / LearningItem / ListItem. Legacy aliases
(`Project`, `ProjectItem`, `TodoItem`) stay for existing call sites. Table and
column names are unchanged.
"""

from app.models.orm.attachments import Attachment, AttachmentChunk, MessageChunk
from app.models.orm.chat import Chat, Message
from app.models.orm.integrations import (
    PushToken,
    SuggestedReminder,
    UserCalendarConnection,
    UserGmailConnection,
)
from app.models.orm.learning import Learning, LearningItem, QuizMissEvent, VocabDeck, VocabEntry
from app.models.orm.lists import ListItem
from app.models.orm.memory import Memory
from app.models.orm.suggestions import Suggestion
from app.models.orm.usage import ProductEvent, UsageDaily
from app.models.orm.user import User

Project = Learning
ProjectItem = LearningItem
TodoItem = ListItem

__all__ = [
    "Attachment",
    "AttachmentChunk",
    "Chat",
    "Learning",
    "LearningItem",
    "ListItem",
    "Memory",
    "Message",
    "MessageChunk",
    "ProductEvent",
    "Project",
    "ProjectItem",
    "PushToken",
    "QuizMissEvent",
    "SuggestedReminder",
    "Suggestion",
    "TodoItem",
    "UsageDaily",
    "User",
    "UserCalendarConnection",
    "UserGmailConnection",
    "VocabDeck",
    "VocabEntry",
]
