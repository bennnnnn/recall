"""Compatibility import for module-owned My Job ORM models."""

from app.modules.job_search.models import JobMatch, JobSearchProfile

__all__ = ["JobMatch", "JobSearchProfile"]
