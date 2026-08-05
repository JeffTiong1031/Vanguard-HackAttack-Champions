"""Regression: Render deploy must not block port bind or poison the request connection.

Root cause (2026-08-05): migrate_schema(get_conn()) ran on the process singleton
inside asyncio.wait_for(..., 45s). Timeout left the migrate thread racing request
handlers on the same psycopg2 connection → InFailedSqlTransaction; the 45s wait
kept uvicorn from binding → Render health-check flaps.
"""
import inspect
import os

import app.main as main_mod
from app.db import (
    connect,
    migrate_on_dedicated_connection,
    status_constraint_is_current,
)
from app.deps import get_conn


def test_migrate_opens_dedicated_connection_not_request_singleton(monkeypatch):
    """Migrations must never touch the request-path singleton connection."""
    shared = get_conn()
    opened: list = []

    real_connect = connect

    def tracking_connect(dsn: str, **kwargs):
        conn = real_connect(dsn, **kwargs)
        opened.append(conn)
        return conn

    monkeypatch.setattr("app.db.connect", tracking_connect)
    migrate_on_dedicated_connection(os.environ["DATABASE_URL"])

    assert opened, "expected a dedicated connection to be opened"
    assert all(c is not shared for c in opened)
    assert all(c._conn.closed for c in opened), "dedicated migrate conn must be closed"


def test_status_constraint_is_current_detects_extended_check():
    """Skip DROP/ADD when the extended status CHECK is already in place."""
    conn = get_conn()
    assert status_constraint_is_current(conn, "org_llm_policy_status_check") is True
    assert status_constraint_is_current(conn, "no_such_constraint_ever") is False


def test_startup_does_not_await_migration():
    """Port bind must not wait on migrate — Render health checks the open port."""
    src = inspect.getsource(main_mod._startup)
    assert "wait_for" not in src
    assert "create_task" in src or "ensure_future" in src


def test_migrate_leaves_shared_connection_usable():
    """After migrate on a dedicated conn, the singleton must still accept SQL."""
    shared = get_conn()
    migrate_on_dedicated_connection(os.environ["DATABASE_URL"])
    row = shared.execute("SELECT 1 AS n").fetchone()
    shared.commit()
    assert row["n"] == 1
