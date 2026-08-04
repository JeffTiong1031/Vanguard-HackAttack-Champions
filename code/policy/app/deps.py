"""Shared application state.

The connection lives here rather than in main.py so route modules can import
get_conn() without importing the app itself -- main.py imports the routers, so
the reverse import would be a cycle that works only by statement ordering.

DATABASE_URL (Supabase Postgres connection string) is read from the environment.
Copy .env.example → .env and fill in your Supabase credentials for local dev.
"""
import os

from dotenv import load_dotenv

from app.db import connect, init_schema
from app.seed import seed_registry

# Load .env when present (local dev). In production set DATABASE_URL directly
# in the host environment (Render / Railway / etc.).
load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. "
        "Copy .env.example → .env and add your Supabase connection string, "
        "or set the environment variable before starting the server."
    )

_conn = connect(DATABASE_URL)
init_schema(_conn)
seed_registry(_conn)


def get_conn():
    return _conn
