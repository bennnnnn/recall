"""Compatibility alias for the packaged implementation."""

import sys

from app.services.learning import path_seed as _impl
from app.services.learning.path_seed import seed_language_path as seed_language_path

sys.modules[__name__] = _impl
