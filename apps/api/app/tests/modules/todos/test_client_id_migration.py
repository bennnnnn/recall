"""Migration 0138 runs again after a deploy it half-applied (review of #2621).

The concurrent index build runs outside the migration's transaction: a build that failed left
the column added and the revision not stamped, so the next deploy's ``add_column`` failed, and
``IF NOT EXISTS`` kept the invalid unique index, which enforces nothing. Each statement is
read here against a recording ``op``; up, down, up and a rerun over a half-applied deploy were
run on the local test database.
"""

import contextlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


def _migration():
    path = Path(__file__).resolve().parents[4] / "alembic/versions/0138_todo_client_id.py"
    spec = importlib.util.spec_from_file_location("todo_client_id_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _recording_op(index_valid: bool | None):
    statements: list[str] = []

    def execute(statement, *_args, **_kwargs):
        statements.append(str(statement))

    bind = SimpleNamespace(
        execute=lambda *_a, **_k: SimpleNamespace(scalar=lambda: index_valid),
    )
    op = SimpleNamespace(
        execute=execute,
        get_bind=lambda: bind,
        get_context=lambda: SimpleNamespace(autocommit_block=contextlib.nullcontext),
    )
    return op, statements


@pytest.mark.parametrize("index_valid", [None, True, False])
def test_upgrade_adds_nothing_twice_and_rebuilds_an_invalid_index(monkeypatch, index_valid):
    migration = _migration()
    op, statements = _recording_op(index_valid)
    monkeypatch.setattr(migration, "op", op)
    migration.upgrade()
    assert statements[0] == "ALTER TABLE todo_items ADD COLUMN IF NOT EXISTS client_id UUID"
    dropped = "DROP INDEX CONCURRENTLY IF EXISTS uq_todo_user_client_id" in statements
    # Only a half-built (invalid) index is dropped: a valid one is kept, none is built new.
    assert dropped is (index_valid is False)
    assert statements[-1].startswith(
        "CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_todo_user_client_id"
    )


def test_downgrade_runs_again_over_a_half_downgraded_table(monkeypatch):
    migration = _migration()
    op, statements = _recording_op(None)
    monkeypatch.setattr(migration, "op", op)
    migration.downgrade()
    assert statements == [
        "DROP INDEX CONCURRENTLY IF EXISTS uq_todo_user_client_id",
        "ALTER TABLE todo_items DROP COLUMN IF EXISTS client_id",
    ]
