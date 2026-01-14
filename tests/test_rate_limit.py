import unittest
from app.services.rate_limit import RateLimiter

class TestRateLimiter(unittest.TestCase):
    def test_allow(self):
        rl = RateLimiter()
        self.assertTrue(rl.allow(1, 2, "p_post"))
        self.assertFalse(rl.allow(1, 2, "p_post"))
