from __future__ import annotations
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class AppConfig:
    discord_token: str
    database_path: str
    sync_guild_id: int | None

    @staticmethod
    def from_env() -> "AppConfig":
        token = (os.getenv("DISCORD_TOKEN") or "").strip()
        if not token:
            raise RuntimeError("DISCORD_TOKEN is required")
        db = (os.getenv("DATABASE_PATH") or "/data/profile.db").strip() or "/data/profile.db"
        gid = (os.getenv("SYNC_GUILD_ID") or "").strip()
        sync_gid = int(gid) if gid.isdigit() else None
        return AppConfig(token, db, sync_gid)
