"""SQLAlchemy mapped models. Prefer `from app.models.orm import User`.

Learning classes map to the `projects` / `project_items` tables. Schedule
exports `TodoItem`. Database table and column names are unchanged.
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
from app.models.orm.learning_practice import LearningPracticeEvent
from app.models.orm.memory import Memory
from app.models.orm.schedule import TodoItem
from app.models.orm.suggestions import Suggestion
from app.models.orm.usage import ProductEvent, UsageDaily
from app.models.orm.user import User

__all__ = [
    "Attachment",
    "AttachmentChunk",
    "Chat",
    "Learning",
    "LearningItem",
    "LearningPracticeEvent",
    "Memory",
    "Message",
    "MessageChunk",
    "ProductEvent",
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
