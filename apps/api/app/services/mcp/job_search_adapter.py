"""Compatibility import for the My Job chat tool."""

from app.modules.job_search.tool import (
    JOB_DIRECT_REPLY_PREFIX,
    JobSearchAdapter,
    bind_job_search_context,
)

__all__ = [
    "JOB_DIRECT_REPLY_PREFIX",
    "JobSearchAdapter",
    "bind_job_search_context",
]
