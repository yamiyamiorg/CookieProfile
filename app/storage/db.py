from __future__ import annotations
import asyncio
import sqlite3
from datetime import datetime, timezone
from typing import Optional
from ..models import ProfileData, GuildConfigData

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

def dt_to_str(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()

def str_to_dt(s: str) -> datetime:
    return datetime.fromisoformat(s)

class Database:
    def __init__(self, path: str):
        self.path = path
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        def _open() -> sqlite3.Connection:
            conn = sqlite3.connect(self.path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            return conn
        self._conn = await asyncio.to_thread(_open)
        await self._migrate()

    async def close(self) -> None:
        if self._conn:
            conn = self._conn
            self._conn = None
            await asyncio.to_thread(conn.close)

    @property
    def conn(self) -> sqlite3.Connection:
        if not self._conn:
            raise RuntimeError("DB not connected")
        return self._conn

    async def _exec(self, sql: str, params: tuple = ()) -> None:
        async with self._lock:
            def _run():
                cur = self.conn.execute(sql, params)
                self.conn.commit()
                cur.close()
            await asyncio.to_thread(_run)

    async def _fetchone(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        async with self._lock:
            def _run():
                cur = self.conn.execute(sql, params)
                row = cur.fetchone()
                cur.close()
                return row
            return await asyncio.to_thread(_run)

    async def _fetchall(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        async with self._lock:
            def _run():
                cur = self.conn.execute(sql, params)
                rows = cur.fetchall()
                cur.close()
                return rows
            return await asyncio.to_thread(_run)

    async def _migrate(self) -> None:
        await self._exec("""
        CREATE TABLE IF NOT EXISTS guild_config(
            guild_id INTEGER PRIMARY KEY,
            channel_id INTEGER,
            log_channel_id INTEGER,
            panel_message_id INTEGER
        )
        """)
        await self._exec("""
        CREATE TABLE IF NOT EXISTS profiles(
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL DEFAULT '',
            condition TEXT NOT NULL DEFAULT '',
            hobby TEXT NOT NULL DEFAULT '',
            care TEXT NOT NULL DEFAULT '',
            one TEXT NOT NULL DEFAULT '',
            state TEXT NOT NULL DEFAULT '通常',
            state_updated_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            public_message_id INTEGER,
            PRIMARY KEY (guild_id, user_id)
        )
        """)
        # ---- schema migration (backward compatible) ----
        # Older deployments may have different column names. We add missing columns in-place.
        cols = await self._fetchall("PRAGMA table_info(guild_config)")
        colnames = {r["name"] for r in cols}

        if "channel_id" not in colnames:
            await self._exec("ALTER TABLE guild_config ADD COLUMN channel_id INTEGER")
            # If legacy column exists, backfill.
            legacy_cols = {r["name"] for r in await self._fetchall("PRAGMA table_info(guild_config)")}
            if "panel_channel_id" in legacy_cols:
                await self._exec("UPDATE guild_config SET channel_id = panel_channel_id WHERE channel_id IS NULL AND panel_channel_id IS NOT NULL")

        # Ensure other expected columns exist
        cols2 = await self._fetchall("PRAGMA table_info(guild_config)")
        colnames2 = {r["name"] for r in cols2}
        if "log_channel_id" not in colnames2:
            await self._exec("ALTER TABLE guild_config ADD COLUMN log_channel_id INTEGER")
        if "panel_message_id" not in colnames2:
            await self._exec("ALTER TABLE guild_config ADD COLUMN panel_message_id INTEGER")

        pcols = await self._fetchall("PRAGMA table_info(profiles)")
        pnames = {r["name"] for r in pcols}
        if "public_message_id" not in pnames:
            await self._exec("ALTER TABLE profiles ADD COLUMN public_message_id INTEGER")

        # ---- data migration: state labels ----
        has_legacy_energy = await self._fetchone("SELECT 1 FROM profiles WHERE state='省エネ' LIMIT 1")
        await self._exec("UPDATE profiles SET state='元気' WHERE state='好調'")
        await self._exec("UPDATE profiles SET state='通常' WHERE state='普通'")
        await self._exec("UPDATE profiles SET state='しんどい' WHERE state='不調'")
        await self._exec("UPDATE profiles SET state='低速' WHERE state='省エネ'")
        if has_legacy_energy:
            await self._exec("UPDATE profiles SET state='しんどい' WHERE state='休憩'")
        else:
            await self._exec("UPDATE profiles SET state='低速' WHERE state='休憩'")

    # config
    async def get_guild_config(self, guild_id: int) -> GuildConfigData:
        row = await self._fetchone("SELECT * FROM guild_config WHERE guild_id=?", (guild_id,))
        if not row:
            return GuildConfigData(guild_id, None, None, None)
        return GuildConfigData(
            guild_id=row["guild_id"],
            channel_id=row["channel_id"],
            log_channel_id=row["log_channel_id"],
            panel_message_id=row["panel_message_id"],
        )

    async def set_guild_config(self, guild_id: int, *, channel_id: int, log_channel_id: int | None) -> None:
        await self._exec("""
        INSERT INTO guild_config(guild_id, channel_id, log_channel_id, panel_message_id)
        VALUES(?,?,?,NULL)
        ON CONFLICT(guild_id) DO UPDATE SET
            channel_id=excluded.channel_id,
            log_channel_id=excluded.log_channel_id
        """, (guild_id, channel_id, log_channel_id))

    async def set_panel_message_id(self, guild_id: int, message_id: int | None) -> None:
        await self._exec("""
        INSERT INTO guild_config(guild_id, panel_message_id) VALUES(?,?)
        ON CONFLICT(guild_id) DO UPDATE SET panel_message_id=excluded.panel_message_id
        """, (guild_id, message_id))

    # profiles
    async def get_profile(self, guild_id: int, user_id: int) -> ProfileData:
        row = await self._fetchone("SELECT * FROM profiles WHERE guild_id=? AND user_id=?", (guild_id, user_id))
        if not row:
            now = utcnow()
            await self._exec("""
            INSERT INTO profiles(guild_id, user_id, state_updated_at, updated_at)
            VALUES(?,?,?,?)
            """, (guild_id, user_id, dt_to_str(now), dt_to_str(now)))
            row = await self._fetchone("SELECT * FROM profiles WHERE guild_id=? AND user_id=?", (guild_id, user_id))
        assert row is not None
        return ProfileData(
            guild_id=row["guild_id"],
            user_id=row["user_id"],
            name=row["name"],
            condition=row["condition"],
            hobby=row["hobby"],
            care=row["care"],
            one=row["one"],
            state=row["state"],
            state_updated_at=str_to_dt(row["state_updated_at"]),
            updated_at=str_to_dt(row["updated_at"]),
            public_message_id=row["public_message_id"],
        )

    async def update_profile_fields(self, guild_id: int, user_id: int, *, name: str, condition: str, hobby: str, care: str, one: str) -> None:
        now = utcnow()
        await self._exec("""
        UPDATE profiles SET
            name=?,
            condition=?,
            hobby=?,
            care=?,
            one=?,
            updated_at=?
        WHERE guild_id=? AND user_id=?
        """, (name, condition, hobby, care, one, dt_to_str(now), guild_id, user_id))

    async def update_state(self, guild_id: int, user_id: int, state: str) -> None:
        now = utcnow()
        await self._exec("""
        UPDATE profiles SET state=?, state_updated_at=?
        WHERE guild_id=? AND user_id=?
        """, (state, dt_to_str(now), guild_id, user_id))

    async def set_public_message_id(self, guild_id: int, user_id: int, message_id: int | None) -> None:
        await self._exec("""
        UPDATE profiles SET public_message_id=?
        WHERE guild_id=? AND user_id=?
        """, (message_id, guild_id, user_id))
