class ChatServiceError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class QuotaExceededError(ChatServiceError):
    pass


class SpendCapReachedError(ChatServiceError):
    """Today's global spend cap (``DAILY_GLOBAL_SPEND_USD``) is reached; no turn starts.

    Not a ``QuotaExceededError``: the user's own allowance is not used up, so
    the transports send the plain error event (this message), not the quota
    code that opens the upgrade prompt.
    """


class ChatNotFoundError(ChatServiceError):
    pass


class ChatBusyError(ChatServiceError):
    """Another turn is already preparing/streaming on this chat.

    Transports map this to ``code: "busy"`` (same as same-socket rejection).
    """

    def __init__(
        self,
        message: str = "Still generating — wait or cancel first.",
    ) -> None:
        super().__init__(message)


class AttachmentValidationError(ChatServiceError):
    pass


class ConsentRequiredError(ChatServiceError):
    """The account has not agreed to what goes to outside AI services, or withdrew.

    Chat transports send ``code: "consent_required"`` and HTTP answers 403 with
    the same code; the phone opens its consent screen (``modules/account/consent.py``).
    """

    code = "consent_required"

    def __init__(
        self,
        message: str = "Agree to how Recall uses outside AI services to continue.",
    ) -> None:
        super().__init__(message)


class UnknownModelOverrideError(ChatServiceError):
    """Per-message picker asked for an alias the user's pool does not include."""

    def __init__(self, alias: str) -> None:
        self.alias = alias
        super().__init__(f"Unknown or unavailable model: {alias}")


class RedisUnavailableError(Exception):
    """Redis is required for auth revocation / quota; outage → fail closed with 503.

    Distinct from ChatServiceError so transports can return ``unavailable`` / 503
    with Retry-After instead of a generic 500 or a misleading 401.
    """

    def __init__(
        self,
        message: str = "Service temporarily unavailable. Please retry shortly.",
    ) -> None:
        self.message = message
        super().__init__(message)


class PushTokenBindError(Exception):
    """Cross-user push-token rebind rejected (missing or mismatched device_id)."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)
