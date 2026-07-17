from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.schemas.common import ResponseStyle, ResponseTone
from app.services import model_catalog


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    name: str | None
    avatar_url: str | None
    default_model: str
    plan: str = "free"
    enabled_models: list[str] | None = None
    response_style: str
    response_tone: str = "funny"
    memory_enabled: bool
    push_notifications_enabled: bool = True
    email_reminders_enabled: bool = False
    reminder_lead_minutes: int = 10
    locale: str = "en"
    timezone: str = "UTC"
    location: str | None = None
    location_enabled: bool = False
    custom_instructions: str | None = None
    age: int | None = None
    country: str | None = None
    job: str | None = None
    created_at: datetime


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    default_model: str | None = None
    enabled_models: list[str] | None = None
    response_style: ResponseStyle | None = None
    response_tone: ResponseTone | None = None
    memory_enabled: bool | None = None
    push_notifications_enabled: bool | None = None
    email_reminders_enabled: bool | None = None
    reminder_lead_minutes: int | None = Field(default=None, ge=5, le=60)
    locale: str | None = None
    timezone: str | None = Field(default=None, max_length=64)
    location: str | None = Field(default=None, max_length=128)
    location_enabled: bool | None = None
    custom_instructions: str | None = Field(default=None, max_length=1000)
    age: int | None = Field(default=None, ge=13, le=120)
    country: str | None = Field(default=None, max_length=64)
    job: str | None = Field(default=None, max_length=128)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        from app.services.profile import normalize_display_name

        normalized = normalize_display_name(value)
        if not normalized:
            raise ValueError("Name must be 1\u201380 characters.")
        return normalized

    @field_validator("default_model")
    @classmethod
    def validate_default_model(cls, value: str | None) -> str | None:
        if value is None:
            return None
        model_catalog.validate_user_alias(value, allow_auto=True)
        return value

    @field_validator("enabled_models")
    @classmethod
    def validate_enabled_models(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if not value:
            raise ValueError("Turn on Auto or at least one model.")
        for entry in value:
            if entry == "auto":
                continue
            model_catalog.validate_user_alias(entry)
        return value

    @field_validator("reminder_lead_minutes")
    @classmethod
    def validate_reminder_lead_minutes(cls, value: int | None) -> int | None:
        if value is None:
            return None
        if value not in {5, 10, 15, 30, 60}:
            raise ValueError("reminder_lead_minutes must be 5, 10, 15, 30, or 60")
        return value

    @field_validator("custom_instructions")
    @classmethod
    def validate_custom_instructions(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None

    @field_validator("country", "job")
    @classmethod
    def validate_optional_profile_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None

    @field_validator("locale")
    @classmethod
    def validate_locale(cls, value: str | None) -> str | None:
        if value is None:
            return None
        # Empty/whitespace locale → no change (treat as unset), matching the
        # custom_instructions blank-clears behavior.
        if not value.strip():
            return None
        from app.services.locale import LOCALE_NAMES, normalize_locale_code

        code = normalize_locale_code(value)
        if code not in LOCALE_NAMES:
            supported = ", ".join(sorted(LOCALE_NAMES))
            raise ValueError(f"Unsupported locale code. Supported: {supported}.")
        return code


class GoogleAuthRequest(BaseModel):
    id_token: str


class AppleAuthRequest(BaseModel):
    id_token: str
    name: str | None = None


class DevAuthRequest(BaseModel):
    email: str = "dev@recall.local"
    name: str = "bini"


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: str | None = None
