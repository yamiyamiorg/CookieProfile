import unittest
from datetime import datetime, timezone

from app.models import ProfileData
from app.services.vc_autopost import should_autopost

class TestVCAutoPost(unittest.TestCase):
    def _profile(self, enabled: int) -> ProfileData:
        now = datetime.now(timezone.utc)
        return ProfileData(
            guild_id=1,
            user_id=2,
            name="test",
            condition="",
            hobby="",
            care="",
            one="",
            state="通常",
            state_updated_at=now,
            updated_at=now,
            public_message_id=None,
            vc_autopost_enabled=enabled,
        )

    def test_should_autopost_on(self):
        prof = self._profile(1)
        self.assertTrue(should_autopost(prof))

    def test_should_autopost_off(self):
        prof = self._profile(0)
        self.assertFalse(should_autopost(prof))
