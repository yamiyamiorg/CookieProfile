from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime

STATE_CHOICES = ("好調", "通常", "省エネ", "休憩")

@dataclass
class ProfileData:
    guild_id: int
    user_id: int
    name: str
    condition: str
    hobby: str
    care: str
    one: str
    state: str
    state_updated_at: datetime
    updated_at: datetime
    public_message_id: int | None  # profile message in configured channel

@dataclass
class GuildConfigData:
    guild_id: int
    channel_id: int | None         # the configured channel for sticky + profiles
    log_channel_id: int | None
    panel_message_id: int | None   # sticky entry message id
