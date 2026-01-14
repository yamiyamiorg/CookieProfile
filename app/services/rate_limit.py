from __future__ import annotations
import time
from dataclasses import dataclass
from typing import Dict, Tuple

@dataclass(frozen=True)
class RateLimits:
    modal_save_sec: int = 60
    state_change_sec: int = 20
    p_confirm_sec: int = 20
    p_post_sec: int = 120
    panel_bump_sec: int = 30  # bump at most once per 30s per guild

DEFAULT_LIMITS = RateLimits()

class RateLimiter:
    def __init__(self, limits: RateLimits = DEFAULT_LIMITS):
        self.limits = limits
        self._last: Dict[Tuple[int,int,str], float] = {}

    def _window(self, action: str) -> int:
        return {
            "modal_save": self.limits.modal_save_sec,
            "state_change": self.limits.state_change_sec,
            "p_confirm": self.limits.p_confirm_sec,
            "p_post": self.limits.p_post_sec,
            "panel_bump": self.limits.panel_bump_sec,
        }.get(action, 0)

    def allow(self, guild_id: int, user_id: int, action: str) -> bool:
        w = self._window(action)
        if w <= 0:
            return True
        now = time.time()
        k = (guild_id, user_id, action)
        last = self._last.get(k)
        if last is None or (now - last) >= w:
            self._last[k] = now
            return True
        return False
