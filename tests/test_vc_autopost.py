import time
import unittest

from app.services.vc_autopost import VCAutoPostLimiter

class TestVCAutoPostLimiter(unittest.TestCase):
    def test_global_cooldown_blocks_other_vc(self):
        limiter = VCAutoPostLimiter(global_cooldown_sec=5, vc_cooldown_sec=10)
        self.assertTrue(limiter.allow(1, 2, 100))
        self.assertFalse(limiter.allow(1, 2, 101))

    def test_vc_cooldown_blocks_same_vc(self):
        limiter = VCAutoPostLimiter(global_cooldown_sec=5, vc_cooldown_sec=10)
        self.assertTrue(limiter.allow(1, 2, 100))
        limiter._last_global[(1, 2)] = time.time() - 6
        limiter._last_vc[(1, 2, 100)] = time.time() - 1
        self.assertFalse(limiter.allow(1, 2, 100))
