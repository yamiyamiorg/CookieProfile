from __future__ import annotations
from datetime import datetime
from typing import Optional

def fmt_ts(dt: datetime) -> str:
    return dt.strftime("%Y/%m/%d %H:%M")

def make_log_line(
    *,
    ts: datetime,
    guild_id: int,
    user_id: int,
    action: str,
    channel_id: Optional[int],
    result: str,
    reason: Optional[str] = None,
) -> str:
    line = f"[Profile] ts={fmt_ts(ts)} guild={guild_id} user={user_id} action={action} channel={channel_id if channel_id is not None else '-'} result={result}"
    if reason:
        line += f" reason={reason}"
    return line
