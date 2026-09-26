"""Keep ``app.services.math.*`` identical to ``app.modules.math.*``."""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import sys
from types import ModuleType

_LEGACY = "app.services.math"
_CANONICAL = "app.modules.math"


class _AliasLoader(importlib.abc.Loader):
    def __init__(self, module: ModuleType) -> None:
        self._module = module

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> ModuleType:
        return self._module

    def exec_module(self, module: ModuleType) -> None:
        return None


class _AliasFinder(importlib.abc.MetaPathFinder):
    def find_spec(
        self,
        fullname: str,
        path: object = None,
        target: object = None,
    ) -> importlib.machinery.ModuleSpec | None:
        if fullname != _LEGACY and not fullname.startswith(f"{_LEGACY}."):
            return None
        if fullname in sys.modules:
            return None
        canonical = _CANONICAL + fullname.removeprefix(_LEGACY)
        # Do not insert the module into sys.modules here. Importlib treats a
        # module that appears during find_spec as already loaded and then
        # reuses its original spec, which re-executes the file.
        real = importlib.import_module(canonical)
        return importlib.util.spec_from_loader(fullname, _AliasLoader(real))


def install(legacy_name: str) -> None:
    """Register submodule aliases. The legacy package object must keep its own name."""
    del legacy_name
    if not any(isinstance(finder, _AliasFinder) for finder in sys.meta_path):
        sys.meta_path.insert(0, _AliasFinder())
