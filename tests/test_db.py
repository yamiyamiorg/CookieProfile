import unittest
import os, tempfile
from app.storage.db import Database, utcnow

class TestDB(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False)
        self.tmp.close()
        self.db = Database(self.tmp.name)
        await self.db.connect()

    async def asyncTearDown(self):
        await self.db.close()
        os.unlink(self.tmp.name)

    async def test_profile_create(self):
        p = await self.db.get_profile(1, 2)
        self.assertEqual(p.state, "通常")
        await self.db.update_state(1, 2, "元気")
        p2 = await self.db.get_profile(1, 2)
        self.assertEqual(p2.state, "元気")

    async def test_config(self):
        await self.db.set_guild_config(1, channel_id=10, log_channel_id=None)
        cfg = await self.db.get_guild_config(1)
        self.assertEqual(cfg.channel_id, 10)
