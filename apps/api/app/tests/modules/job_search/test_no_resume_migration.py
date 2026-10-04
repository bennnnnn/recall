"""Retired résumé storage cannot influence future jobs; other records remain intact."""

import importlib.util
from pathlib import Path
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text

MIGRATION = Path(__file__).resolve().parents[4] / "alembic/versions/0103_remove_job_resume.py"


async def test_resume_columns_removed_and_affected_revisions_invalidated(db_session):
    schema = f"job_no_resume_{uuid4().hex}"
    await db_session.execute(text(f'CREATE SCHEMA "{schema}"'))
    await db_session.execute(text(f'SET LOCAL search_path TO "{schema}"'))
    await db_session.execute(text("CREATE TABLE attachments (id uuid PRIMARY KEY, filename text)"))
    await db_session.execute(
        text("""
        CREATE TABLE job_search_profiles (
            id integer PRIMARY KEY, revision integer, skills json, status text,
            resume_attachment_id uuid REFERENCES attachments(id), resume_filename text,
            resume_text text, resume_profile json
        )
    """)
    )
    attachment_id = uuid4()
    await db_session.execute(
        text("INSERT INTO attachments VALUES (:id,'document.pdf')"), {"id": attachment_id}
    )
    await db_session.execute(
        text("""
            INSERT INTO job_search_profiles VALUES
            (1,3,'["SQL"]','paused',:id,'document.pdf','Resume text','{"skills":["Python"]}'),
            (2,7,'["Care"]','active',NULL,NULL,NULL,NULL)
        """),
        {"id": attachment_id},
    )
    spec = importlib.util.spec_from_file_location("job_no_resume_migration", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def upgrade(sync_session):
        with Operations.context(MigrationContext.configure(sync_session.connection())):
            module.upgrade()

    await db_session.run_sync(upgrade)
    rows = (
        (await db_session.execute(text("SELECT * FROM job_search_profiles ORDER BY id")))
        .mappings()
        .all()
    )
    assert [dict(row) for row in rows] == [
        {"id": 1, "revision": 4, "skills": ["SQL"], "status": "paused"},
        {"id": 2, "revision": 7, "skills": ["Care"], "status": "active"},
    ]
    assert (
        await db_session.scalar(
            text("SELECT filename FROM attachments WHERE id=:id"), {"id": attachment_id}
        )
        == "document.pdf"
    )
    await db_session.execute(text("SET LOCAL search_path TO public"))
    await db_session.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
