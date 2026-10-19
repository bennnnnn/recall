from typing import Literal

from pydantic import BaseModel, Field

from app.models.schemas.text import UserText


class PushTokenIn(BaseModel):
    expo_push_token: UserText = Field(min_length=8, max_length=512)
    platform: UserText = Field(min_length=2, max_length=20)
    device_id: UserText | None = Field(default=None, max_length=128)
    # "split" created the first three channels. "tone" created the v2 channels
    # that play the bundled cue. Older installs omit this.
    android_channels: Literal["split", "tone"] | None = None
