import os
import sqlite3
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT, duration REAL DEFAULT 0, scope TEXT, bugs INTEGER DEFAULT 0,
    status TEXT, total INTEGER DEFAULT 0, passed INTEGER DEFAULT 0,
    failed INTEGER DEFAULT 0, skipped INTEGER DEFAULT 0, output TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS results (
    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER, tc_id TEXT, name TEXT, suite TEXT,
    status TEXT, duration REAL, expected TEXT, actual TEXT, reason TEXT, severity TEXT,
    category TEXT, screenshot TEXT, suggestion TEXT, suggestion_source TEXT, timestamp TEXT
);
CREATE TABLE IF NOT EXISTS cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT, batch TEXT, story TEXT, tc_id TEXT, scenario TEXT,
    input TEXT, expected TEXT, kind TEXT, api_spec TEXT, approved INTEGER DEFAULT 0,
    automated INTEGER DEFAULT 0, created_at TEXT
);
"""


def path():
    return os.environ.get("DASHBOARD_DB", str(ROOT / "dashboard.db"))


def _conn():
    c = sqlite3.connect(path(), timeout=15)
    c.row_factory = sqlite3.Row
    return c


def init():
    with closing(_conn()) as c:
        c.executescript(SCHEMA)
        c.commit()


def query(sql, args=()):
    with closing(_conn()) as c:
        return c.execute(sql, args).fetchall()


def one(sql, args=()):
    rows = query(sql, args)
    return rows[0] if rows else None


def execute(sql, args=()):
    with closing(_conn()) as c:
        cur = c.execute(sql, args)
        c.commit()
        return cur.lastrowid


def executemany(sql, rows):
    with closing(_conn()) as c:
        c.executemany(sql, rows)
        c.commit()
