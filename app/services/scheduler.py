from __future__ import annotations
import asyncio
import discord
from ..storage.db import Database

class DeleteScheduler:
    """
    Periodically deletes messages scheduled in DB.
    Uses REST delete by (channel_id, message_id) to avoid relying on fetch_message().
    """
    def __init__(self, bot: discord.Client, db: Database):
        self.bot = bot
        self.db = db
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    def start(self) -> None:
        if self._task:
            return
        self._task = asyncio.create_task(self._run(), name="delete-scheduler")

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            try:
                await asyncio.wait([self._task], timeout=5)
            finally:
                self._task = None

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                due = await self.db.due_deletes(limit=50)
                for guild_id, channel_id, message_id, _ in due:
                    await self._delete_one(guild_id, channel_id, message_id)
            except Exception:
                pass
            await asyncio.sleep(15)

    async def _delete_one(self, guild_id: int, channel_id: int, message_id: int) -> None:
        try:
            await self.bot.http.delete_message(channel_id, message_id)  # type: ignore[attr-defined]
        except discord.NotFound:
            pass
        except discord.Forbidden:
            pass
        except Exception:
            # transient: keep for retry
            return
        finally:
            await self.db.remove_scheduled_delete(guild_id, channel_id, message_id)
