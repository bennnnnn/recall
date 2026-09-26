"""My Job module.

Consumers should import the smallest public surface they need, such as
``app.modules.job_search.service`` or ``app.modules.job_search.chat_intent``.
The package initializer stays dependency-free so SQLAlchemy can discover the
module-owned models without creating an import cycle.
"""
