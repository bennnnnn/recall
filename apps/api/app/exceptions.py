class ChatServiceError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class QuotaExceededError(ChatServiceError):
    pass


class ChatNotFoundError(ChatServiceError):
    pass


class AttachmentValidationError(ChatServiceError):
    pass


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
