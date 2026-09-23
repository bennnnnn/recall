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
from app.models.orm.suggestions import Suggestion
from app.models.orm.usage import ProductEvent, UsageDaily
from app.models.orm.user import User
from app.modules.job_search.models import JobMatch, JobSearchProfile
from app.modules.learning.models import (
    Learning,
    LearningItem,
    LearningPracticeEvent,
    QuizMissEvent,
    VocabDeck,
    VocabEntry,
)
from app.modules.memory.models import Memory
from app.modules.todos.models import TodoItem

__all__ = [
    "Attachment",
    "AttachmentChunk",
    "Chat",
    "JobMatch",
    "JobSearchProfile",
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
