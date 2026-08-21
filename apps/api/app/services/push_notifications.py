"""Compatibility alias for the packaged implementation."""

import sys

from app.services.notifications import push as _impl
from app.services.notifications.push import (
    EMAIL_SUGGESTION_PUSH_LIMIT as EMAIL_SUGGESTION_PUSH_LIMIT,
)
from app.services.notifications.push import (
    LEARNING_REDIS_PREFIX as LEARNING_REDIS_PREFIX,
)
from app.services.notifications.push import (
    MAX_REMINDER_LEAD_MINUTES as MAX_REMINDER_LEAD_MINUTES,
)
from app.services.notifications.push import (
    OVERDUE_MAX_HOURS as OVERDUE_MAX_HOURS,
)
from app.services.notifications.push import (
    RECEIPT_MAX_AGE_SECONDS as RECEIPT_MAX_AGE_SECONDS,
)
from app.services.notifications.push import (
    RECEIPT_MIN_AGE_SECONDS as RECEIPT_MIN_AGE_SECONDS,
)
from app.services.notifications.push import (
    RECEIPT_PENDING_ZSET as RECEIPT_PENDING_ZSET,
)
from app.services.notifications.push import (
    UTC as UTC,
)
from app.services.notifications.push import (
    UUID as UUID,
)
from app.services.notifications.push import (
    Any as Any,
)
from app.services.notifications.push import (
    AsyncSession as AsyncSession,
)
from app.services.notifications.push import (
    OutboundPush as OutboundPush,
)
from app.services.notifications.push import (
    PushToken as PushToken,
)
from app.services.notifications.push import (
    Redis as Redis,
)
from app.services.notifications.push import (
    Settings as Settings,
)
from app.services.notifications.push import (
    SuggestedReminder as SuggestedReminder,
)
from app.services.notifications.push import (
    TodoItem as TodoItem,
)
from app.services.notifications.push import (
    User as User,
)
from app.services.notifications.push import (
    UserCalendarConnection as UserCalendarConnection,
)
from app.services.notifications.push import (
    annotations as annotations,
)
from app.services.notifications.push import (
    calendar_nudge_service as calendar_nudge_service,
)
from app.services.notifications.push import (
    calendar_service as calendar_service,
)
from app.services.notifications.push import (
    collect_push_outbound as collect_push_outbound,
)
from app.services.notifications.push import (
    dataclass as dataclass,
)
from app.services.notifications.push import (
    datetime as datetime,
)
from app.services.notifications.push import (
    dispatch_expo as dispatch_expo,
)
from app.services.notifications.push import (
    enqueue_push_receipts as enqueue_push_receipts,
)
from app.services.notifications.push import (
    exists as exists,
)
from app.services.notifications.push import (
    expo_push_gateway as expo_push_gateway,
)
from app.services.notifications.push import (
    field as field,
)
from app.services.notifications.push import (
    finalize_push_deliveries as finalize_push_deliveries,
)
from app.services.notifications.push import (
    google_calendar_gateway as google_calendar_gateway,
)
from app.services.notifications.push import (
    learning_nudges as learning_nudges,
)
from app.services.notifications.push import (
    logger as logger,
)
from app.services.notifications.push import (
    logging as logging,
)
from app.services.notifications.push import (
    normalize_locale_code as normalize_locale_code,
)
from app.services.notifications.push import (
    poll_deferred_push_receipts as poll_deferred_push_receipts,
)
from app.services.notifications.push import (
    process_calendar_nudges as process_calendar_nudges,
)
from app.services.notifications.push import (
    process_email_suggestions as process_email_suggestions,
)
from app.services.notifications.push import (
    process_learning_nudges as process_learning_nudges,
)
from app.services.notifications.push import (
    process_todo_reminders as process_todo_reminders,
)
from app.services.notifications.push import (
    push_repo as push_repo,
)
from app.services.notifications.push import (
    reminder_title as reminder_title,
)
from app.services.notifications.push import (
    resolve_reminder_lead_minutes as resolve_reminder_lead_minutes,
)
from app.services.notifications.push import (
    run_push_cycle as run_push_cycle,
)
from app.services.notifications.push import (
    select as select,
)
from app.services.notifications.push import (
    should_notify_todo as should_notify_todo,
)
from app.services.notifications.push import (
    time as time,
)
from app.services.notifications.push import (
    timedelta as timedelta,
)

sys.modules[__name__] = _impl
