"""Compatibility alias for the packaged implementation."""

import sys

from app.services.learning import quiz as _impl
from app.services.learning.quiz import (
    MAX_QUIZ_TRIES_PER_QUESTION as MAX_QUIZ_TRIES_PER_QUESTION,
)
from app.services.learning.quiz import (
    ParsedVocabQuiz as ParsedVocabQuiz,
)
from app.services.learning.quiz import (
    QuizAnswerGrade as QuizAnswerGrade,
)
from app.services.learning.quiz import (
    get_settings as get_settings,
)
from app.services.learning.quiz import (
    is_vocab_quiz_answer as is_vocab_quiz_answer,
)
from app.services.learning.quiz import (
    litellm_gateway as litellm_gateway,
)
from app.services.learning.quiz import (
    match_choice_letter as match_choice_letter,
)
from app.services.learning.quiz import (
    parse_vocab_quiz as parse_vocab_quiz,
)
from app.services.learning.quiz import (
    quiz_answer_letter as quiz_answer_letter,
)
from app.services.learning.quiz import (
    re as re,
)
from app.services.learning.quiz import (
    strip_vocab_session_metadata as strip_vocab_session_metadata,
)
from app.services.learning.quiz import (
    verified_correct_letter as verified_correct_letter,
)

sys.modules[__name__] = _impl
