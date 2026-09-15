"""لایه‌ی پایگاه‌داده (SQLite) ربات آسترا.

همه‌ی چیزهایی که باید بین ری‌استارت‌ها بماند اینجا ذخیره می‌شود:
کاربران، اشتراک VIP، وضعیت گفتگو، گروه‌ها، آمار، لاگ خطاها و پرداخت‌ها.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from .. import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id      TEXT PRIMARY KEY,
    first_name   TEXT DEFAULT '',
    username     TEXT DEFAULT '',
    chat_type    TEXT DEFAULT 'private',
    joined_at    INTEGER DEFAULT 0,
    last_seen    INTEGER DEFAULT 0,
    msg_count    INTEGER DEFAULT 0,
    vip_until    INTEGER DEFAULT 0,
    nav_stack    TEXT DEFAULT '[]',
    is_blocked   INTEGER DEFAULT 0,
    referred_by  TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS states (
    user_id  TEXT PRIMARY KEY,
    state    TEXT DEFAULT '',
    data     TEXT DEFAULT '{}',
    updated  INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS groups (
    group_id     TEXT PRIMARY KEY,
    title        TEXT DEFAULT '',
    welcome_text TEXT DEFAULT '',
    anti_link    INTEGER DEFAULT 0,
    anti_spam    INTEGER DEFAULT 0,
    del_forward  INTEGER DEFAULT 0,
    locked       INTEGER DEFAULT 0,
    max_warn     INTEGER DEFAULT 3,
    added_at     INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS warns (
    group_id TEXT NOT NULL,
    user_id  TEXT NOT NULL,
    count    INTEGER DEFAULT 0,
    reason   TEXT DEFAULT '',
    updated  INTEGER DEFAULT 0,
    PRIMARY KEY (group_id, user_id)
);
CREATE TABLE IF NOT EXISTS group_stats (
    group_id  TEXT NOT NULL,
    user_id   TEXT NOT NULL,
    messages  INTEGER DEFAULT 0,
    last_seen INTEGER DEFAULT 0,
    PRIMARY KEY (group_id, user_id)
);
CREATE TABLE IF NOT EXISTS playlist (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  TEXT NOT NULL,
    title    TEXT NOT NULL,
    artist   TEXT DEFAULT '',
    url      TEXT DEFAULT '',
    added_at INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS usage (
    key   TEXT PRIMARY KEY,
    count INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS usage_daily (
    user_id TEXT NOT NULL,
    day     TEXT NOT NULL,
    key     TEXT NOT NULL,
    count   INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, day, key)
);
CREATE TABLE IF NOT EXISTS payments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT NOT NULL,
    plan       TEXT NOT NULL,
    amount     TEXT DEFAULT '',
    status     TEXT DEFAULT 'pending',
    receipt    TEXT DEFAULT '',
    created_at INTEGER DEFAULT 0,
    decided_at INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS logs (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      INTEGER DEFAULT 0,
    level   TEXT DEFAULT 'ERROR',
    where_  TEXT DEFAULT '',
    message TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS games (
    chat_id  TEXT PRIMARY KEY,
    kind     TEXT DEFAULT 'dooz',
    board    TEXT DEFAULT '---------',
    turn     TEXT DEFAULT 'x',
    level    TEXT DEFAULT 'hard',
    mode     TEXT DEFAULT 'bot',
    players  TEXT DEFAULT '{}',
    chat_id2 TEXT DEFAULT '',
    history  TEXT DEFAULT '[]',
    started  INTEGER DEFAULT 0,
    first    TEXT DEFAULT 'user',
    updated  INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS scores (
    user_id TEXT NOT NULL,
    kind    TEXT DEFAULT 'dooz',
    win     INTEGER DEFAULT 0,
    lose    INTEGER DEFAULT 0,
    draw    INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, kind)
);
CREATE TABLE IF NOT EXISTS anon_links (
    token    TEXT PRIMARY KEY,
    owner    TEXT NOT NULL,
    created  INTEGER DEFAULT 0,
    expires  INTEGER DEFAULT 0,
    used_by  TEXT DEFAULT '',
    status   TEXT DEFAULT 'active',
    uses     INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS anon_chats (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    token    TEXT NOT NULL,
    user_a   TEXT NOT NULL,
    user_b   TEXT NOT NULL,
    started  INTEGER DEFAULT 0,
    last_msg INTEGER DEFAULT 0,
    status   TEXT DEFAULT 'open',
    reveal_a INTEGER DEFAULT 0,
    reveal_b INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS anon_msgs (
    chat_id  TEXT NOT NULL,
    msg_id   TEXT NOT NULL,
    target   TEXT DEFAULT '',
    created  INTEGER DEFAULT 0,
    PRIMARY KEY (chat_id, msg_id)
);
CREATE TABLE IF NOT EXISTS anon_blocks (
    user_id    TEXT NOT NULL,
    blocked_id TEXT NOT NULL,
    created    INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, blocked_id)
);
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_usage_day ON usage_daily(day);
"""


def _now() -> int:
    return int(time.time())


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


class Database:
    """یک نگهدارنده‌ی ساده و امن (Thread-safe) برای SQLite."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = str(path or config.DB_PATH)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False, timeout=30)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(_SCHEMA)
        self._migrate()
        self._conn.commit()

    def _migrate(self) -> None:
        """افزودن ستون‌های جدید به جداولِ دیتابیس‌های قدیمی (بدون خراب کردن داده‌ها)."""
        wanted = {
            "games": {"history": "TEXT DEFAULT '[]'", "started": "INTEGER DEFAULT 0",
                      "first": "TEXT DEFAULT 'user'"},
        }
        for table, columns in wanted.items():
            existing = {row["name"] for row in
                        self._query_all(f"PRAGMA table_info({table})")}
            for column, definition in columns.items():
                if column not in existing:
                    try:
                        self._conn.execute(
                            f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
                    except sqlite3.Error:
                        pass

    # ------------------------------------------------------------------ #
    # ابزارهای داخلی
    # ------------------------------------------------------------------ #
    def _execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(query, params)
            self._conn.commit()
            return cur

    def _query_one(self, query: str, params: tuple = ()) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute(query, params).fetchone()

    def _query_all(self, query: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(query, params).fetchall()

    # ------------------------------------------------------------------ #
    # کاربران
    # ------------------------------------------------------------------ #
    def touch_user(self, user_id: str, first_name: str = "", username: str = "",
                   chat_type: str = "private") -> None:
        row = self._query_one("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        now = _now()
        if row is None:
            self._execute(
                "INSERT INTO users (user_id, first_name, username, chat_type, joined_at, last_seen)"
                " VALUES (?,?,?,?,?,?)",
                (user_id, first_name, username, chat_type, now, now),
            )
        else:
            self._execute(
                "UPDATE users SET last_seen = ?, msg_count = msg_count + 1"
                " WHERE user_id = ?",
                (now, user_id),
            )
            if first_name:
                self._execute("UPDATE users SET first_name = ? WHERE user_id = ?",
                              (first_name, user_id))
            if username:
                self._execute("UPDATE users SET username = ? WHERE user_id = ?",
                              (username, user_id))

    def get_user(self, user_id: str) -> dict | None:
        row = self._query_one("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return dict(row) if row else None

    def count_users(self) -> int:
        row = self._query_one("SELECT COUNT(*) AS c FROM users")
        return int(row["c"]) if row else 0

    def active_users(self, days: int = 7) -> int:
        row = self._query_one(
            "SELECT COUNT(*) AS c FROM users WHERE last_seen >= ?",
            (_now() - days * 86400,),
        )
        return int(row["c"]) if row else 0

    def all_user_ids(self) -> list[str]:
        return [r["user_id"] for r in self._query_all(
            "SELECT user_id FROM users WHERE is_blocked = 0")]

    def set_blocked(self, user_id: str, blocked: bool = True) -> None:
        self._execute("UPDATE users SET is_blocked = ? WHERE user_id = ?",
                      (1 if blocked else 0, user_id))

    # ------------------------------------------------------------------ #
    # اشتراک ویژه
    # ------------------------------------------------------------------ #
    def vip_until(self, user_id: str) -> int:
        row = self._query_one("SELECT vip_until FROM users WHERE user_id = ?", (user_id,))
        return int(row["vip_until"]) if row else 0

    def grant_vip(self, user_id: str, days: int) -> int:
        """افزودن ‎days‎ روز به اشتراک؛ تاریخ انقضای جدید را برمی‌گرداند."""
        base = max(self.vip_until(user_id), _now())
        until = base + int(days) * 86400
        self._execute("INSERT OR IGNORE INTO users (user_id, joined_at, last_seen) VALUES (?,?,?)",
                      (user_id, _now(), _now()))
        self._execute("UPDATE users SET vip_until = ? WHERE user_id = ?", (until, user_id))
        return until

    def revoke_vip(self, user_id: str) -> None:
        self._execute("UPDATE users SET vip_until = 0 WHERE user_id = ?", (user_id,))

    def vip_users(self) -> list[dict]:
        rows = self._query_all(
            "SELECT * FROM users WHERE vip_until > ? ORDER BY vip_until DESC LIMIT 100",
            (_now(),),
        )
        return [dict(r) for r in rows]

    def count_vip(self) -> int:
        row = self._query_one("SELECT COUNT(*) AS c FROM users WHERE vip_until > ?", (_now(),))
        return int(row["c"]) if row else 0

    # ------------------------------------------------------------------ #
    # وضعیت گفتگو (State Machine)
    # ------------------------------------------------------------------ #
    def set_state(self, user_id: str, state: str, data: dict | None = None) -> None:
        self._execute(
            "INSERT INTO states (user_id, state, data, updated) VALUES (?,?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET state=excluded.state, "
            "data=excluded.data, updated=excluded.updated",
            (user_id, state, json.dumps(data or {}, ensure_ascii=False), _now()),
        )

    def get_state(self, user_id: str) -> tuple[str, dict]:
        row = self._query_one("SELECT state, data FROM states WHERE user_id = ?", (user_id,))
        if not row:
            return "", {}
        try:
            data = json.loads(row["data"] or "{}")
        except json.JSONDecodeError:
            data = {}
        return row["state"] or "", data

    def clear_state(self, user_id: str) -> None:
        self._execute("DELETE FROM states WHERE user_id = ?", (user_id,))

    # ------------------------------------------------------------------ #
    # منوی پیمایش (برای دکمه‌ی بازگشت)
    # ------------------------------------------------------------------ #
    def push_nav(self, user_id: str, route: str, depth: int = 6) -> None:
        row = self._query_one("SELECT nav_stack FROM users WHERE user_id = ?", (user_id,))
        stack: list[str] = []
        if row and row["nav_stack"]:
            try:
                stack = json.loads(row["nav_stack"])
            except json.JSONDecodeError:
                stack = []
        if stack and stack[-1] == route:
            return
        stack.append(route)
        stack = stack[-depth:]
        self._execute(
            "INSERT OR IGNORE INTO users (user_id, joined_at, last_seen) VALUES (?,?,?)",
            (user_id, _now(), _now()),
        )
        self._execute("UPDATE users SET nav_stack = ? WHERE user_id = ?",
                      (json.dumps(stack, ensure_ascii=False), user_id))

    def pop_nav(self, user_id: str, fallback: str = "nav:home") -> str:
        row = self._query_one("SELECT nav_stack FROM users WHERE user_id = ?", (user_id,))
        stack: list[str] = []
        if row and row["nav_stack"]:
            try:
                stack = json.loads(row["nav_stack"])
            except json.JSONDecodeError:
                stack = []
        if not stack:
            return fallback
        stack.pop()
        self._execute("UPDATE users SET nav_stack = ? WHERE user_id = ?",
                      (json.dumps(stack, ensure_ascii=False), user_id))
        return stack[-1] if stack else fallback

    def peek_nav(self, user_id: str, fallback: str = "nav:home") -> str:
        row = self._query_one("SELECT nav_stack FROM users WHERE user_id = ?", (user_id,))
        if row and row["nav_stack"]:
            try:
                stack = json.loads(row["nav_stack"])
            except json.JSONDecodeError:
                return fallback
            if stack:
                return stack[-1]
        return fallback

    # ------------------------------------------------------------------ #
    # گروه‌ها
    # ------------------------------------------------------------------ #
    def ensure_group(self, group_id: str, title: str = "") -> None:
        self._execute(
            "INSERT OR IGNORE INTO groups (group_id, title, added_at) VALUES (?,?,?)",
            (group_id, title, _now()),
        )
        if title:
            self._execute("UPDATE groups SET title = ? WHERE group_id = ?", (title, group_id))

    def get_group(self, group_id: str) -> dict | None:
        row = self._query_one("SELECT * FROM groups WHERE group_id = ?", (group_id,))
        return dict(row) if row else None

    def set_group(self, group_id: str, **fields) -> None:
        if not fields:
            return
        cols = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [group_id]
        self._execute(f"UPDATE groups SET {cols} WHERE group_id = ?", tuple(values))

    def add_warn(self, group_id: str, user_id: str, reason: str = "") -> int:
        self._execute(
            "INSERT INTO warns (group_id, user_id, count, reason, updated) VALUES (?,?,1,?,?) "
            "ON CONFLICT(group_id, user_id) DO UPDATE SET count = count + 1, "
            "reason = excluded.reason, updated = excluded.updated",
            (group_id, user_id, reason, _now()),
        )
        row = self._query_one(
            "SELECT count FROM warns WHERE group_id = ? AND user_id = ?", (group_id, user_id))
        return int(row["count"]) if row else 1

    def reset_warn(self, group_id: str, user_id: str) -> None:
        self._execute("DELETE FROM warns WHERE group_id = ? AND user_id = ?", (group_id, user_id))

    def get_warn(self, group_id: str, user_id: str) -> int:
        row = self._query_one(
            "SELECT count FROM warns WHERE group_id = ? AND user_id = ?", (group_id, user_id))
        return int(row["count"]) if row else 0

    def bump_group_stat(self, group_id: str, user_id: str) -> None:
        self._execute(
            "INSERT INTO group_stats (group_id, user_id, messages, last_seen) VALUES (?,?,1,?) "
            "ON CONFLICT(group_id, user_id) DO UPDATE SET messages = messages + 1, "
            "last_seen = excluded.last_seen",
            (group_id, user_id, _now()),
        )

    def group_top(self, group_id: str, limit: int = 5) -> list[dict]:
        rows = self._query_all(
            "SELECT * FROM group_stats WHERE group_id = ? ORDER BY messages DESC LIMIT ?",
            (group_id, limit),
        )
        return [dict(r) for r in rows]

    def group_members_count(self, group_id: str) -> int:
        row = self._query_one(
            "SELECT COUNT(*) AS c FROM group_stats WHERE group_id = ?", (group_id,))
        return int(row["c"]) if row else 0

    # ------------------------------------------------------------------ #
    # پلی‌لیست
    # ------------------------------------------------------------------ #
    def playlist_add(self, user_id: str, title: str, artist: str = "", url: str = "") -> bool:
        if self.playlist_count(user_id) >= 100:
            return False
        self._execute(
            "INSERT INTO playlist (user_id, title, artist, url, added_at) VALUES (?,?,?,?,?)",
            (user_id, title, artist, url, _now()),
        )
        return True

    def playlist_count(self, user_id: str) -> int:
        row = self._query_one("SELECT COUNT(*) AS c FROM playlist WHERE user_id = ?", (user_id,))
        return int(row["c"]) if row else 0

    def playlist_list(self, user_id: str, limit: int = 50) -> list[dict]:
        rows = self._query_all(
            "SELECT * FROM playlist WHERE user_id = ? ORDER BY added_at DESC LIMIT ?",
            (user_id, limit),
        )
        return [dict(r) for r in rows]

    def playlist_remove(self, user_id: str, item_id: int) -> None:
        self._execute("DELETE FROM playlist WHERE user_id = ? AND id = ?", (user_id, item_id))

    def playlist_clear(self, user_id: str) -> None:
        self._execute("DELETE FROM playlist WHERE user_id = ?", (user_id,))

    # ------------------------------------------------------------------ #
    # آمار و محدودیت‌ها
    # ------------------------------------------------------------------ #
    def bump_usage(self, key: str, amount: int = 1) -> None:
        self._execute(
            "INSERT INTO usage (key, count) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET count = count + excluded.count",
            (key, amount),
        )

    def bump_daily(self, user_id: str, key: str) -> int:
        day = _today()
        self._execute(
            "INSERT INTO usage_daily (user_id, day, key, count) VALUES (?,?,?,1) "
            "ON CONFLICT(user_id, day, key) DO UPDATE SET count = count + 1",
            (user_id, day, key),
        )
        row = self._query_one(
            "SELECT count FROM usage_daily WHERE user_id = ? AND day = ? AND key = ?",
            (user_id, day, key),
        )
        return int(row["count"]) if row else 1

    def daily_count(self, user_id: str, key: str) -> int:
        row = self._query_one(
            "SELECT count FROM usage_daily WHERE user_id = ? AND day = ? AND key = ?",
            (user_id, _today(), key),
        )
        return int(row["count"]) if row else 0

    def usage_stats(self, limit: int = 15) -> list[tuple[str, int]]:
        rows = self._query_all("SELECT key, count FROM usage ORDER BY count DESC LIMIT ?", (limit,))
        return [(r["key"], int(r["count"])) for r in rows]

    # ------------------------------------------------------------------ #
    # پرداخت‌ها
    # ------------------------------------------------------------------ #
    def add_payment(self, user_id: str, plan: str, amount: str = "") -> int:
        cur = self._execute(
            "INSERT INTO payments (user_id, plan, amount, status, created_at) VALUES (?,?,?,?,?)",
            (user_id, plan, amount, "pending", _now()),
        )
        return int(cur.lastrowid or 0)

    def set_payment(self, payment_id: int, status: str, receipt: str = "") -> dict | None:
        self._execute(
            "UPDATE payments SET status = ?, receipt = ?, decided_at = ? WHERE id = ?",
            (status, receipt, _now(), payment_id),
        )
        row = self._query_one("SELECT * FROM payments WHERE id = ?", (payment_id,))
        return dict(row) if row else None

    def get_payment(self, payment_id: int) -> dict | None:
        row = self._query_one("SELECT * FROM payments WHERE id = ?", (payment_id,))
        return dict(row) if row else None

    def pending_payments(self, limit: int = 20) -> list[dict]:
        rows = self._query_all(
            "SELECT * FROM payments WHERE status = 'pending' ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------ #
    # لاگ خطاها
    # ------------------------------------------------------------------ #
    def log(self, level: str, where_: str, message: str) -> None:
        try:
            self._execute(
                "INSERT INTO logs (ts, level, where_, message) VALUES (?,?,?,?)",
                (_now(), level.upper(), where_, message[:2000]),
            )
            # فقط ۵۰۰ رکورد آخر نگه داشته می‌شود
            self._execute(
                "DELETE FROM logs WHERE id NOT IN (SELECT id FROM logs ORDER BY id DESC LIMIT 500)"
            )
        except sqlite3.Error:  # پایگاه‌داده نباید باعث کرش ربات شود
            pass

    def recent_logs(self, level: str | None = None, limit: int = 15) -> list[dict]:
        if level and level.upper() != "ALL":
            rows = self._query_all(
                "SELECT * FROM logs WHERE level = ? ORDER BY id DESC LIMIT ?",
                (level.upper(), limit),
            )
        else:
            rows = self._query_all("SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------ #
    # تنظیمات (روشن/خاموش کردن بخش‌ها)
    # ------------------------------------------------------------------ #
    def get_setting(self, key: str, default: str = "") -> str:
        row = self._query_one("SELECT value FROM settings WHERE key = ?", (key,))
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self._execute(
            "INSERT INTO settings (key, value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    def section_enabled(self, section: str) -> bool:
        value = self.get_setting(f"section:{section}", "")
        if value == "":
            return config.DEFAULT_SECTION_STATE.get(section, True)
        return value == "1"

    def set_section(self, section: str, enabled: bool) -> None:
        self.set_setting(f"section:{section}", "1" if enabled else "0")

    # ------------------------------------------------------------------ #
    # ------------------------------------------------------------------ #
    # بازی‌ها (دوز و بقیه)
    # ------------------------------------------------------------------ #
    def save_game(self, chat_id: str, **fields) -> None:
        fields.setdefault("kind", "dooz")
        fields.setdefault("board", "-" * 9)
        fields.setdefault("turn", "x")
        fields.setdefault("level", "hard")
        fields.setdefault("mode", "bot")
        fields.setdefault("players", "{}")
        fields.setdefault("chat_id2", "")
        fields.setdefault("history", "[]")
        fields.setdefault("started", 0)
        fields.setdefault("first", "user")
        keys = ["kind", "board", "turn", "level", "mode", "players", "chat_id2",
                "history", "started", "first"]
        keys = [k for k in keys if k in fields]
        keys.append("updated")
        values = [fields[k] for k in keys[:-1]] + [_now()]
        sets = ", ".join(f"{k}=excluded.{k}" for k in keys)
        marks = ", ".join("?" for _ in keys)
        self._execute(
            f"INSERT INTO games (chat_id, {', '.join(keys)}) VALUES (?, {marks}) "
            f"ON CONFLICT(chat_id) DO UPDATE SET {sets}",
            (str(chat_id), *values),
        )

    def load_game(self, chat_id: str) -> dict | None:
        row = self._query_one("SELECT * FROM games WHERE chat_id = ?", (str(chat_id),))
        return dict(row) if row else None

    def clear_game(self, chat_id: str) -> None:
        self._execute("DELETE FROM games WHERE chat_id = ?", (str(chat_id),))

    def bump_score(self, user_id: str, field: str, kind: str = "dooz") -> None:
        if field not in ("win", "lose", "draw"):
            return
        self._execute(
            "INSERT INTO scores (user_id, kind, win, lose, draw) VALUES (?,?,0,0,0) "
            "ON CONFLICT DO NOTHING", (str(user_id), kind))
        self._execute(f"UPDATE scores SET {field} = {field} + 1 WHERE user_id = ? AND kind = ?",
                      (str(user_id), kind))

    def game_score(self, user_id: str, kind: str = "dooz") -> dict:
        row = self._query_one(
            "SELECT win, lose, draw FROM scores WHERE user_id = ? AND kind = ?",
            (str(user_id), kind))
        return dict(row) if row else {"win": 0, "lose": 0, "draw": 0}

    def top_scores(self, kind: str = "dooz", limit: int = 10) -> list[dict]:
        rows = self._query_all(
            "SELECT user_id, win, lose, draw FROM scores WHERE kind = ? "
            "ORDER BY win DESC, draw DESC LIMIT ?", (kind, limit))
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------ #
    # چت ناشناس
    # ------------------------------------------------------------------ #
    def anon_create_link(self, owner: str, hours: int = 24) -> str:
        import secrets
        token = secrets.token_urlsafe(9).replace("-", "").replace("_", "")[:12]
        now = _now()
        self._execute(
            "INSERT INTO anon_links (token, owner, created, expires, status, uses)"
            " VALUES (?,?,?,?, 'active', 0)",
            (token, str(owner), now, now + max(1, int(hours)) * 3600))
        return token

    def anon_link(self, token: str) -> dict | None:
        row = self._query_one("SELECT * FROM anon_links WHERE token = ?", (str(token),))
        return dict(row) if row else None

    def anon_owner_links(self, owner: str, limit: int = 8) -> list[dict]:
        rows = self._query_all(
            "SELECT * FROM anon_links WHERE owner = ? ORDER BY created DESC LIMIT ?",
            (str(owner), limit))
        return [dict(r) for r in rows]

    def anon_set_status(self, token: str, status: str) -> None:
        self._execute("UPDATE anon_links SET status = ? WHERE token = ?", (status, str(token)))

    def anon_use_link(self, token: str, user_id: str) -> None:
        self._execute(
            "UPDATE anon_links SET uses = uses + 1, used_by = ?, status = 'used' WHERE token = ?",
            (str(user_id), str(token)))

    def anon_open_chat(self, token: str, user_a: str, user_b: str) -> int:
        now = _now()
        cur = self._execute(
            "INSERT INTO anon_chats (token, user_a, user_b, started, last_msg, status)"
            " VALUES (?,?,?,?,?, 'open')",
            (str(token), str(user_a), str(user_b), now, now))
        return int(cur.lastrowid or 0)

    def anon_chat(self, chat_row_id: int) -> dict | None:
        row = self._query_one("SELECT * FROM anon_chats WHERE id = ?", (int(chat_row_id),))
        return dict(row) if row else None

    def anon_active_chat(self, user_id: str) -> dict | None:
        row = self._query_one(
            "SELECT * FROM anon_chats WHERE status = 'open' AND (user_a = ? OR user_b = ?)"
            " ORDER BY last_msg DESC LIMIT 1",
            (str(user_id), str(user_id)))
        return dict(row) if row else None

    def anon_close_chat(self, chat_row_id: int) -> None:
        self._execute("UPDATE anon_chats SET status = 'closed' WHERE id = ?", (int(chat_row_id),))

    def anon_touch_chat(self, chat_row_id: int) -> None:
        self._execute("UPDATE anon_chats SET last_msg = ? WHERE id = ?", (_now(), int(chat_row_id)))

    def anon_set_reveal(self, chat_row_id: int, user_id: str) -> None:
        row = self.anon_chat(chat_row_id)
        if not row:
            return
        field = "reveal_a" if str(row["user_a"]) == str(user_id) else "reveal_b"
        self._execute(f"UPDATE anon_chats SET {field} = 1 WHERE id = ?", (int(chat_row_id),))

    def anon_block(self, user_id: str, blocked_id: str) -> None:
        self._execute(
            "INSERT INTO anon_blocks (user_id, blocked_id, created) VALUES (?,?,?) "
            "ON CONFLICT DO NOTHING", (str(user_id), str(blocked_id), _now()))

    def anon_unblock(self, user_id: str, blocked_id: str) -> None:
        self._execute("DELETE FROM anon_blocks WHERE user_id = ? AND blocked_id = ?",
                      (str(user_id), str(blocked_id)))

    def anon_is_blocked(self, user_id: str, blocked_id: str) -> bool:
        row = self._query_one(
            "SELECT 1 AS c FROM anon_blocks WHERE user_id = ? AND blocked_id = ?",
            (str(user_id), str(blocked_id)))
        return bool(row)

    def anon_map_msg(self, chat_id: str, msg_id: str, target: str) -> None:
        if not msg_id or not target:
            return
        self._execute(
            "INSERT INTO anon_msgs (chat_id, msg_id, target, created) VALUES (?,?,?,?) "
            "ON CONFLICT(chat_id, msg_id) DO UPDATE SET target=excluded.target",
            (str(chat_id), str(msg_id), str(target), _now()))

    def anon_reply_target(self, chat_id: str, msg_id: str) -> str:
        row = self._query_one(
            "SELECT target FROM anon_msgs WHERE chat_id = ? AND msg_id = ?",
            (str(chat_id), str(msg_id)))
        return str(row["target"] or "") if row else ""

    def anon_prune(self, older_than_days: int = 3) -> None:
        limit = _now() - older_than_days * 86400
        self._execute("DELETE FROM anon_msgs WHERE created < ?", (limit,))
        self._execute("DELETE FROM anon_links WHERE expires < ?", (limit,))
        self._execute(
            "UPDATE anon_chats SET status = 'expired' WHERE status = 'open' AND last_msg < ?",
            (_now() - 3 * 86400,))

    def anon_count(self) -> dict:
        open_chats = self._query_one(
            "SELECT COUNT(*) AS c FROM anon_chats WHERE status = 'open'")
        links = self._query_one(
            "SELECT COUNT(*) AS c FROM anon_links WHERE status = 'active'")
        return {"open": int(open_chats["c"]) if open_chats else 0,
                "links": int(links["c"]) if links else 0}



    def close(self) -> None:
        with self._lock:
            self._conn.close()


# نمونه‌ی سراسری (در کل برنامه یک اتصال استفاده می‌شود)
DB = Database()


def humanize_expiry(until_ts: int) -> str:
    """نمایش خوش‌خوانِ زمان باقی‌مانده‌ی اشتراک."""
    if until_ts <= 0:
        return "ندارد"
    delta = until_ts - _now()
    if delta <= 0:
        return "منقضی شده"
    days = delta // 86400
    if days >= 30:
        return f"{days // 30} ماه و {days % 30} روز"
    if days >= 1:
        return f"{days} روز"
    hours = max(1, delta // 3600)
    return f"{hours} ساعت"
