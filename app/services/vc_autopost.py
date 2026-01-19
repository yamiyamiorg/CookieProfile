from __future__ import annotations
import time
from typing import Dict, Tuple

from ..models import ProfileData

def should_autopost(profile: ProfileData) -> bool:
    return bool(profile.vc_autopost_enabled)

class VCAutoPostLimiter:
    def __init__(self, *, global_cooldown_sec: int = 300, vc_cooldown_sec: int = 600):
        self.global_cooldown_sec = global_cooldown_sec
        self.vc_cooldown_sec = vc_cooldown_sec
        self._last_global: Dict[Tuple[int, int], float] = {}
        self._last_vc: Dict[Tuple[int, int, int], float] = {}

    def allow(self, guild_id: int, user_id: int, vc_id: int) -> bool:
        now = time.time()
        gk = (guild_id, user_id)
        vk = (guild_id, user_id, vc_id)
        last_global = self._last_global.get(gk)
        if last_global is not None and (now - last_global) < self.global_cooldown_sec:
            return False
        last_vc = self._last_vc.get(vk)
        if last_vc is not None and (now - last_vc) < self.vc_cooldown_sec:
            return False
        self._last_global[gk] = now
        self._last_vc[vk] = now
        return True
