# Supabase Setup Guide

The Vanguard policy service now stores all data in **Supabase Postgres** instead
of a local SQLite file. Follow these steps once to get up and running.

---

## 1. Create a Supabase project

1. Go to [supabase.com](https://supabase.com) and sign in.
2. Click **New project**, choose a name (e.g. `vanguard-policy`), pick a region,
   set a strong database password, and click **Create new project**.
3. Wait ~2 minutes for provisioning.

---

## 2. Run the schema SQL

1. In your project dashboard, open **SQL Editor** (left sidebar).
2. Click **New query**.
3. Paste the entire contents of [`migrations/001_initial.sql`](migrations/001_initial.sql).
4. Click **Run**. You should see `Success. No rows returned`.

---

## 3. Get your connection string

1. In the dashboard, go to **Project Settings → Database**.
2. Scroll to **Connection string** and select the **URI** tab.
3. Choose **Transaction** mode (port 6543) for Supabase pooler, or **Session**
   mode (port 5432) for direct connection. Either works for this service.
4. Copy the URI — it looks like:
   ```
   postgresql://postgres.xxxxxxxxxxxx:PASSWORD@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
   ```
   Replace `[YOUR-PASSWORD]` with the database password you set in step 1.

---

## 4. Configure local dev

```bash
# In code/policy/
cp .env.example .env
# Then edit .env and paste your connection string as DATABASE_URL
```

Your `.env` file (git-ignored) should look like:
```
DATABASE_URL=postgresql://postgres.xxxx:PASSWORD@...supabase.com:6543/postgres
```

---

## 5. Install dependencies and start the server

```bash
cd code/policy
.venv\Scripts\pip install -e ".[dev]"
.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

On first start the service will:
- Connect to Supabase.
- Run `init_schema` (creates tables if not present — idempotent).
- Seed the LLM registry (8 AI tools, idempotent via `ON CONFLICT DO NOTHING`).

---

## 6. Create your first company

```bash
curl -s -X POST http://localhost:8001/v1/signup \
  -H "Content-Type: application/json" \
  -d '{"company_name": "Acme Corp"}' | python -m json.tool
```

Response:
```json
{
  "org_id": "...",
  "secret": "VG-xxxxxxxxxxxxxxxxxxxxxxxx"
}
```

**Save the `secret` immediately** — it is shown once and never stored in plain text.

---

## 7. Log in to the admin dashboard

Use the secret from step 6 as the **Company Admin Key** on the admin console
login page.

---

## 8. Deploy to Render / Railway

Set the `DATABASE_URL` environment variable in your hosting provider's dashboard.
The server reads it at startup — no code changes needed.

> **Tip**: Use the **Transaction pooler** URL (port 6543) on Render/Railway to
> avoid exhausting Postgres connection limits under load.
