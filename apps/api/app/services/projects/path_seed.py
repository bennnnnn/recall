"""Compatibility alias for the packaged implementation."""

import sys

from app.services.learning import path_seed as _impl
from app.services.learning.path_seed import (
    PATH_MAX_CHAPTERS as PATH_MAX_CHAPTERS,
)
from app.services.learning.path_seed import (
    PATH_MIN_CHAPTERS as PATH_MIN_CHAPTERS,
)
from app.services.learning.path_seed import (
    PATH_SEED_WORD_CAP as PATH_SEED_WORD_CAP,
)
from app.services.learning.path_seed import (
    UUID as UUID,
)
from app.services.learning.path_seed import (
    Any as Any,
)
from app.services.learning.path_seed import (
    BaseModel as BaseModel,
)
from app.services.learning.path_seed import (
    Field as Field,
)
from app.services.learning.path_seed import (
    LanguagePathSeedResult as LanguagePathSeedResult,
)
from app.services.learning.path_seed import (
    LanguagePathWord as LanguagePathWord,
)
from app.services.learning.path_seed import (
    annotations as annotations,
)
from app.services.learning.path_seed import (
    language_display_name as language_display_name,
)
from app.services.learning.path_seed import (
    locale_language as locale_language,
)
from app.services.learning.path_seed import (
    logger as logger,
)
from app.services.learning.path_seed import (
    logging as logging,
)
from app.services.learning.path_seed import (
    normalize_path_titles as normalize_path_titles,
)
from app.services.learning.path_seed import (
    parse_learning_path as parse_learning_path,
)
from app.services.learning.path_seed import (
    seed_language_path as seed_language_path,
)
from app.services.learning.path_seed import (
    starter_path_for_level as starter_path_for_level,
)

sys.modules[__name__] = _impl
