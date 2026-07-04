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
