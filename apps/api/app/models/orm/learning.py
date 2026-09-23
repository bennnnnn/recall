"""Compatibility import for Learning ORM models."""

from app.modules.learning.models import (
    Learning,
    LearningItem,
    LearningPracticeEvent,
    QuizMissEvent,
    VocabDeck,
    VocabEntry,
)

__all__ = [
    "Learning",
    "LearningItem",
    "LearningPracticeEvent",
    "QuizMissEvent",
    "VocabDeck",
    "VocabEntry",
]
