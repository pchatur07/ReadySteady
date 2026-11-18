"""Data-access infrastructure: connections and explicit transactions."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from flask import current_app, g

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect(path):
    # isolation_level=None -> autocommit; we open transactions ourselves with BEGIN IMMEDIATE.
    conn = sqlite3.connect(path, isolation_level=None, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db(conn):
    conn.executescript(SCHEMA_PATH.read_text())


@contextmanager
def transaction(conn):
    """Run a block atomically. BEGIN IMMEDIATE takes the write lock up front, so two
    students ordering the last samosa at the same moment cannot both succeed (NFR-02)."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except Exception:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")
