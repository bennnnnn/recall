"""Remove job stages without dropping jobs, bookmarks, or application notes."""

import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

MIGRATION = Path(__file__).resolve().parents[4] / "alembic/versions/0102_job_applied_only.py"


async def test_removed_stages_become_applied_and_cannot_be_recreated(db_session):
    schema = f"job_applied_migration_{uuid4().hex}"
    await db_session.execute(text(f'CREATE SCHEMA "{schema}"'))
    await db_session.execute(text(f'SET LOCAL search_path TO "{schema}"'))
    await db_session.execute(
        text("""
        CREATE TABLE job_matches (
            id uuid PRIMARY KEY, title text, status text NOT NULL, is_saved boolean, notes text,
            CONSTRAINT ck_job_matches_status CHECK (
                status IN ('new','saved','applied','interviewing','offer','rejected','hidden')
            )
        )
    """)
    )
    original = {}
    for status in ("new", "saved", "applied", "interviewing", "offer", "rejected", "hidden"):
        identifier = uuid4()
        original[identifier] = {
            "id": identifier,
            "title": f"Job {status}",
            "status": status,
            "is_saved": True,
            "notes": "Keep this application note",
        }
        await db_session.execute(
            text("""
            INSERT INTO job_matches (id,title,status,is_saved,notes)
            VALUES (:id,:title,:status,:is_saved,:notes)
        """),
            original[identifier],
        )

    spec = importlib.util.spec_from_file_location("job_applied_migration", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def upgrade(sync_session):
        with Operations.context(MigrationContext.configure(sync_session.connection())):
            module.upgrade()

    await db_session.run_sync(upgrade)
    rows = (await db_session.execute(text("SELECT * FROM job_matches"))).mappings().all()
    assert len(rows) == len(original)
    for row in rows:
        before = original[row["id"]]
        expected = dict(before)
        if before["status"] in {"interviewing", "offer", "rejected"}:
            expected["status"] = "applied"
        assert dict(row) == expected
    for status in ("interviewing", "offer", "rejected"):
        with pytest.raises(IntegrityError):
            async with db_session.begin_nested():
                await db_session.execute(
                    text("UPDATE job_matches SET status=:status WHERE id=:id"),
                    {"status": status, "id": next(iter(original))},
                )
    await db_session.execute(text("SET LOCAL search_path TO public"))
    await db_session.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
