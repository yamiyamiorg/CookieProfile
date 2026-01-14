import unittest
from datetime import datetime
from app.services.audit import make_log_line

class TestAudit(unittest.TestCase):
    def test_format(self):
        line = make_log_line(ts=datetime(2026,1,1,12,0), guild_id=1, user_id=2, action="edit_modal", channel_id=3, result="ok", reason=None)
        self.assertIn("[Profile]", line)
        self.assertIn("guild=1", line)
        self.assertIn("user=2", line)
