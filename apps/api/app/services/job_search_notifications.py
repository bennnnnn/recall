"""Narrow re-export for the packaged My Job notification helper.

The dedicated runner imports this name while the service now lives inside the
``job_search`` package. No generic automation behavior is exposed here.
"""

from app.services.job_search.notifications import notify_job_matches_ready

__all__ = ["notify_job_matches_ready"]
