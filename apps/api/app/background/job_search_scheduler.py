"""Compatibility import for the My Job scheduler."""

from app.modules.job_search.scheduler import (
    start_job_search_scheduler,
    stop_job_search_scheduler,
)

__all__ = ["start_job_search_scheduler", "stop_job_search_scheduler"]
