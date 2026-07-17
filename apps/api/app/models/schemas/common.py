from typing import Literal

from pydantic import BaseModel

MessageRole = Literal["user", "assistant", "system"]

MemoryType = Literal["profile", "preference", "project", "fact", "focus"]

ResponseStyle = Literal["short", "balanced", "detailed"]

ResponseTone = Literal["funny", "professional", "casual", "soft"]

MessageFeedback = Literal["up", "down"]

QuizMode = Literal["exam", "chat"]


class UsageOut(BaseModel):
    date: str
    input_tokens: int
    output_tokens: int
    daily_limit: int
    used_tokens: int
    remaining: int


class ModelInfo(BaseModel):
    id: str
    label: str
    description: str
    tier: str
    plan_access: str = "pro"
    available: bool
    input_price_per_m: float | None = None
    output_price_per_m: float | None = None
    quota_multiplier: float = 1.0
    healthy: bool = True
    latency_p50_ms: int | None = None
    health_samples: int = 0
