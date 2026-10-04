"""Exercise the additive migration on legacy records in an isolated schema."""

import importlib.util
from pathlib import Path
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text

MIGRATION = Path(__file__).resolve().parents[4] / "alembic/versions/0100_job_search_reliability.py"


async def test_migration_preserves_history_and_flags_ambiguous_preferences(db_session):
    schema = f"job_migration_{uuid4().hex}"
    await db_session.execute(text(f'CREATE SCHEMA "{schema}"'))
    await db_session.execute(text(f'SET LOCAL search_path TO "{schema}"'))
    await db_session.execute(
        text("CREATE TABLE users (id uuid PRIMARY KEY, plan text DEFAULT 'pro')")
    )
    await db_session.execute(
        text("""
        CREATE TABLE job_search_profiles (
            id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES users(id),
            location text, salary_min integer, resume_text text, resume_filename text,
            resume_profile json, status text
        )
    """)
    )
    await db_session.execute(
        text("""
        CREATE TABLE job_matches (
            id uuid PRIMARY KEY, profile_id uuid REFERENCES job_search_profiles(id),
            title text, status text, is_saved boolean, notes text
        )
    """)
    )
    user_id, known_id, uncertain_id, match_id = (uuid4() for _ in range(4))
    await db_session.execute(text("INSERT INTO users(id) VALUES (:id)"), {"id": user_id})
    for identifier, location, salary in (
        (known_id, "California", None),
        (uncertain_id, "Springfield", 100000),
    ):
        await db_session.execute(
            text("""
            INSERT INTO job_search_profiles
              (id,user_id,location,salary_min,resume_text,resume_filename,resume_profile,status)
            VALUES (:id,:user,:location,:salary,'Original resume','cv.pdf','{"skills":["SQL"]}','paused')
        """),
            {"id": identifier, "user": user_id, "location": location, "salary": salary},
        )
    await db_session.execute(
        text("""
        INSERT INTO job_matches(id,profile_id,title,status,is_saved,notes)
        VALUES (:id,:profile,'Engineer','interviewing',true,'Call recruiter')
    """),
        {"id": match_id, "profile": known_id},
    )

    spec = importlib.util.spec_from_file_location("my_job_reliability_migration", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def upgrade(sync_session):
        with Operations.context(MigrationContext.configure(sync_session.connection())):
            module.upgrade()

    await db_session.run_sync(upgrade)
    rows = (await db_session.execute(text("SELECT * FROM job_search_profiles"))).mappings().all()
    profiles = {row["id"]: row for row in rows}
    assert profiles[known_id]["country"] == "United States"
    assert profiles[known_id]["included_locations"] == [
        {"country": "United States", "region": "California"}
    ]
    assert not profiles[known_id]["needs_review"]
    assert profiles[uncertain_id]["included_locations"] == []
    assert (
        profiles[uncertain_id]["needs_review"] and profiles[uncertain_id]["salary_currency"] is None
    )
    assert all(
        row["resume_text"] == "Original resume" and row["status"] == "paused" for row in rows
    )
    history = (await db_session.execute(text("SELECT * FROM job_matches"))).mappings().one()
    assert history["id"] == match_id and history["is_saved"]
    assert history["status"] == "interviewing" and history["notes"] == "Call recruiter"
    assert history["assessment_revision"] == 0 and history["match_kind"] == "possible"
    await db_session.execute(text("SET LOCAL search_path TO public"))
    await db_session.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
