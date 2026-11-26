from app.exceptions import (
    ChatBusyError,
    ChatNotFoundError,
    ChatServiceError,
    QuotaExceededError,
    UnknownModelOverrideError,
)


def test_chat_service_errors_carry_message():
    err = ChatServiceError("boom")
    assert err.message == "boom"
    assert str(err) == "boom"
    assert isinstance(QuotaExceededError("q"), ChatServiceError)
    assert isinstance(ChatNotFoundError("missing"), ChatServiceError)
    assert isinstance(ChatBusyError(), ChatServiceError)
    assert ChatBusyError().message.startswith("Still generating")
    unknown = UnknownModelOverrideError("smart-chat")
    assert isinstance(unknown, ChatServiceError)
    assert unknown.alias == "smart-chat"
    assert "smart-chat" in str(unknown)  # the logs name it
    assert "smart-chat" not in unknown.message  # the client never sees an alias


def test_unknown_model_override_error_payload():
    from app.modules.chat.stream_events import error_payload_for_exception

    payload = error_payload_for_exception(UnknownModelOverrideError("glm-5.2"))
    assert payload["type"] == "error"
    assert payload["code"] == "unknown_model"
    # The phone words it from the code; the message names no internal alias (audit,
    # 2026-11-25: "Unknown or unavailable model: glm-5.2" showed in every language).
    assert "glm-5.2" not in payload["message"]
