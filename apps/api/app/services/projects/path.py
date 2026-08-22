"""Compatibility alias for the packaged implementation."""

import sys

from app.services.learning import path as _impl
from app.services.learning.path import (
    CHAPTER_COMPLETE_RATIO as CHAPTER_COMPLETE_RATIO,
)
from app.services.learning.path import (
    CHAPTER_MIN_WORDS as CHAPTER_MIN_WORDS,
)
from app.services.learning.path import (
    DEFAULT_LIST as DEFAULT_LIST,
)
from app.services.learning.path import (
    PATH_MAX_CHAPTERS as PATH_MAX_CHAPTERS,
)
from app.services.learning.path import (
    PATH_MIN_CHAPTERS as PATH_MIN_CHAPTERS,
)
from app.services.learning.path import (
    PATH_SEED_WORD_CAP as PATH_SEED_WORD_CAP,
)
from app.services.learning.path import (
    UUID as UUID,
)
from app.services.learning.path import (
    PathChapterProgress as PathChapterProgress,
)
from app.services.learning.path import (
    Project as Project,
)
from app.services.learning.path import (
    ProjectItem as ProjectItem,
)
from app.services.learning.path import (
    Sequence as Sequence,
)
from app.services.learning.path import (
    annotations as annotations,
)
from app.services.learning.path import (
    append_chapter as append_chapter,
)
from app.services.learning.path import (
    build_path_progress as build_path_progress,
)
from app.services.learning.path import (
    chapter_is_complete as chapter_is_complete,
)
from app.services.learning.path import (
    enqueue_language_path_job as enqueue_language_path_job,
)
from app.services.learning.path import (
    format_path_prompt_lines as format_path_prompt_lines,
)
from app.services.learning.path import (
    is_unspecified_list as is_unspecified_list,
)
from app.services.learning.path import (
    logger as logger,
)
from app.services.learning.path import (
    logging as logging,
)
from app.services.learning.path import (
    normalize_path_titles as normalize_path_titles,
)
from app.services.learning.path import (
    parse_learning_path as parse_learning_path,
)
from app.services.learning.path import (
    resolve_add_list_title as resolve_add_list_title,
)
from app.services.learning.path import (
    sort_list_titles as sort_list_titles,
)
from app.services.learning.path import (
    up_next_chapter as up_next_chapter,
)

sys.modules[__name__] = _impl
