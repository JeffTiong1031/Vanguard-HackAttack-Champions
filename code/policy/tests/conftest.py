"""Point every test at the Supabase database.

DATABASE_URL is read from the environment (or from .env). Tests run against
the real Postgres database — each test that creates data should use unique
identifiers (uuid) to avoid collisions with production data or other tests.

For isolated CI runs, set DATABASE_URL to a dedicated test Supabase project or
a local Postgres instance (e.g. via Docker).

This MUST run before `app.main` is imported, because that module opens its
connection at import time. pytest loads conftest.py first, which is the whole
reason this lives here rather than in a fixture.
"""
import os
from dotenv import load_dotenv

# Load .env so DATABASE_URL is available before app modules are imported.
load_dotenv()

# Confirm DATABASE_URL is present so tests fail fast with a clear message.
if not os.environ.get("DATABASE_URL"):
    raise RuntimeError(
        "DATABASE_URL is not set — tests require a Postgres connection. "
        "Copy .env.example → .env and add your Supabase connection string."
    )
