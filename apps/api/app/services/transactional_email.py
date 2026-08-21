"""Compatibility alias for the packaged implementation."""

import sys

from app.services.notifications import transactional_email as _impl
from app.services.notifications.transactional_email import (
    Any as Any,
)
from app.services.notifications.transactional_email import (
    Settings as Settings,
)
from app.services.notifications.transactional_email import (
    User as User,
)
from app.services.notifications.transactional_email import (
    annotations as annotations,
)
from app.services.notifications.transactional_email import (
    build_learning_nudge as build_learning_nudge,
)
from app.services.notifications.transactional_email import (
    build_receipt as build_receipt,
)
from app.services.notifications.transactional_email import (
    build_todo_reminder as build_todo_reminder,
)
from app.services.notifications.transactional_email import (
    build_welcome as build_welcome,
)
from app.services.notifications.transactional_email import (
    email_gateway as email_gateway,
)
from app.services.notifications.transactional_email import (
    html_lib as html_lib,
)
from app.services.notifications.transactional_email import (
    locale_service as locale_service,
)
from app.services.notifications.transactional_email import (
    logger as logger,
)
from app.services.notifications.transactional_email import (
    logging as logging,
)
from app.services.notifications.transactional_email import (
    send_learning_nudge as send_learning_nudge,
)
from app.services.notifications.transactional_email import (
    send_purchase_receipt as send_purchase_receipt,
)
from app.services.notifications.transactional_email import (
    send_todo_reminder as send_todo_reminder,
)
from app.services.notifications.transactional_email import (
    send_welcome as send_welcome,
)

sys.modules[__name__] = _impl
