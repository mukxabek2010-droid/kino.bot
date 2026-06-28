import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.getenv("DB_PATH", "kinobot.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     INTEGER PRIMARY KEY,
            username    TEXT,
            full_name   TEXT,
            joined_at   TEXT DEFAULT (datetime('now')),
            is_blocked  INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS premium_users (
            user_id     INTEGER PRIMARY KEY,
            expires_at  TEXT NOT NULL,
            activated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS movies (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            code        TEXT UNIQUE NOT NULL,
            title       TEXT NOT NULL,
            is_premium  INTEGER DEFAULT 0,
            file_id     TEXT NOT NULL,
            caption     TEXT,
            added_at    TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS payment_requests (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            status      TEXT DEFAULT 'pending',
            receipt_file_id TEXT,
            created_at  TEXT DEFAULT (datetime('now')),
            reviewed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS stats (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            action      TEXT,
            movie_code  TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        );
    """)

    conn.commit()
    conn.close()


# ─── USERS ────────────────────────────────────────────────────────────────────

def add_user(user_id: int, username: str, full_name: str):
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?,?,?)",
        (user_id, username, full_name)
    )
    conn.execute(
        "UPDATE users SET username=?, full_name=? WHERE user_id=?",
        (username, full_name, user_id)
    )
    conn.commit()
    conn.close()


def get_all_users():
    conn = get_conn()
    rows = conn.execute("SELECT user_id FROM users WHERE is_blocked=0").fetchall()
    conn.close()
    return [r["user_id"] for r in rows]


def get_user_count():
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    return count


# ─── PREMIUM ──────────────────────────────────────────────────────────────────

def is_premium(user_id: int) -> bool:
    conn = get_conn()
    row = conn.execute(
        "SELECT expires_at FROM premium_users WHERE user_id=?", (user_id,)
    ).fetchone()
    conn.close()
    if not row:
        return False
    return datetime.fromisoformat(row["expires_at"]) > datetime.now()


def add_premium(user_id: int, months: int = 1):
    expires = datetime.now() + timedelta(days=30 * months)
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO premium_users (user_id, expires_at) VALUES (?,?)",
        (user_id, expires.isoformat())
    )
    conn.commit()
    conn.close()
    return expires


def remove_premium(user_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM premium_users WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


def get_premium_expires(user_id: int):
    conn = get_conn()
    row = conn.execute(
        "SELECT expires_at FROM premium_users WHERE user_id=?", (user_id,)
    ).fetchone()
    conn.close()
    if row:
        return datetime.fromisoformat(row["expires_at"])
    return None


def get_premium_count():
    conn = get_conn()
    count = conn.execute(
        "SELECT COUNT(*) FROM premium_users WHERE expires_at > datetime('now')"
    ).fetchone()[0]
    conn.close()
    return count


# ─── MOVIES ───────────────────────────────────────────────────────────────────

def add_movie(code: str, title: str, is_premium: int, file_id: str, caption: str = ""):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO movies (code, title, is_premium, file_id, caption) VALUES (?,?,?,?,?)",
            (code, title, is_premium, file_id, caption)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_movie(code: str):
    conn = get_conn()
    row = conn.execute("SELECT * FROM movies WHERE code=?", (code,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_movie(code: str):
    conn = get_conn()
    affected = conn.execute("DELETE FROM movies WHERE code=?", (code,)).rowcount
    conn.commit()
    conn.close()
    return affected > 0


def get_movie_count():
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM movies").fetchone()[0]
    conn.close()
    return count


def get_all_movies(limit=20, offset=0):
    conn = get_conn()
    rows = conn.execute(
        "SELECT code, title, is_premium FROM movies ORDER BY added_at DESC LIMIT ? OFFSET ?",
        (limit, offset)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── PAYMENT REQUESTS ─────────────────────────────────────────────────────────

def create_payment_request(user_id: int, receipt_file_id: str) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO payment_requests (user_id, receipt_file_id) VALUES (?,?)",
        (user_id, receipt_file_id)
    )
    req_id = cur.lastrowid
    conn.commit()
    conn.close()
    return req_id


def get_pending_payments():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM payment_requests WHERE status='pending' ORDER BY created_at"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_payment_status(req_id: int, status: str):
    conn = get_conn()
    conn.execute(
        "UPDATE payment_requests SET status=?, reviewed_at=datetime('now') WHERE id=?",
        (status, req_id)
    )
    conn.commit()
    conn.close()


def get_payment_by_id(req_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM payment_requests WHERE id=?", (req_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ─── STATS ────────────────────────────────────────────────────────────────────

def log_stat(user_id: int, action: str, movie_code: str = ""):
    conn = get_conn()
    conn.execute(
        "INSERT INTO stats (user_id, action, movie_code) VALUES (?,?,?)",
        (user_id, action, movie_code)
    )
    conn.commit()
    conn.close()
