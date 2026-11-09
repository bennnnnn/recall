"""Alembic revision 0128: when the phone last saved the user's place, an expand."""

import importlib.util
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import sqlalchemy as sa

_MIGRATION = Path(__file__).resolve().parents[4] / "alembic/versions/0128_user_location_saved_at.py"


def _migration(op: MagicMock) -> ModuleType:
    spec = importlib.util.spec_from_file_location("location_saved_at_migration", _MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = op  # type: ignore[attr-defined]
    return module


def test_upgrade_only_adds_a_nullable_column_every_row_starts_without():
    op = MagicMock()
    _migration(op).upgrade()
    # No backfill: a place with no time is one no turn trusts until the phone saves it again.
    assert op.execute.call_count == 0 and op.alter_column.call_count == 0
    table, column = op.add_column.call_args.args
    assert table == "users"
    assert column.name == "location_saved_at"
    assert isinstance(column.type, sa.DateTime) and column.type.timezone is True
    assert column.nullable is True and column.server_default is None


def test_downgrade_drops_the_column():
    op = MagicMock()
    _migration(op).downgrade()
    op.drop_column.assert_called_once_with("users", "location_saved_at")


def test_follows_the_last_revision():
    module = _migration(MagicMock())
    assert module.down_revision == "0127_todo_due_has_time"
