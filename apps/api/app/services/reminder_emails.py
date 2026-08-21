"""Compatibility alias for the packaged implementation."""

import sys

from app.services.notifications import reminder_email as _impl
from app.services.notifications.reminder_email import (
    LEARNING_EMAIL_REDIS_PREFIX as LEARNING_EMAIL_REDIS_PREFIX,
)
from app.services.notifications.reminder_email import (
    MAX_REMINDER_LEAD_MINUTES as MAX_REMINDER_LEAD_MINUTES,
)
from app.services.notifications.reminder_email import (
    OVERDUE_MAX_HOURS as OVERDUE_MAX_HOURS,
)
from app.services.notifications.reminder_email import (
    UTC as UTC,
)
from app.services.notifications.reminder_email import (
    AsyncSession as AsyncSession,
)
from app.services.notifications.reminder_email import (
    Redis as Redis,
)
from app.services.notifications.reminder_email import (
    Settings as Settings,
)
from app.services.notifications.reminder_email import (
    TodoItem as TodoItem,
)
from app.services.notifications.reminder_email import (
    User as User,
)
from app.services.notifications.reminder_email import (
    annotations as annotations,
)
from app.services.notifications.reminder_email import (
    datetime as datetime,
)
from app.services.notifications.reminder_email import (
    learning_nudges as learning_nudges,
)
from app.services.notifications.reminder_email import (
    logger as logger,
)
from app.services.notifications.reminder_email import (
    logging as logging,
)
from app.services.notifications.reminder_email import (
    process_learning_nudge_emails as process_learning_nudge_emails,
)
from app.services.notifications.reminder_email import (
    process_todo_reminder_emails as process_todo_reminder_emails,
)
from app.services.notifications.reminder_email import (
    reminder_title as reminder_title,
)
from app.services.notifications.reminder_email import (
    resolve_reminder_lead_minutes as resolve_reminder_lead_minutes,
)
from app.services.notifications.reminder_email import (
    run_email_reminder_cycle as run_email_reminder_cycle,
)
from app.services.notifications.reminder_email import (
    select as select,
)
from app.services.notifications.reminder_email import (
    should_notify_todo as should_notify_todo,
)
from app.services.notifications.reminder_email import (
    timedelta as timedelta,
)
from app.services.notifications.reminder_email import (
    tx_email as tx_email,
)

sys.modules[__name__] = _impl
