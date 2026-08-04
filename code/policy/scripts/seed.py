"""Build the demo world and record every secret/token in DEMO-TOKENS.md.

Run before a demo:  python scripts/seed.py

DEMO / TESTING ONLY. Real deployments never write secrets to disk -- a secret
is shown once and stored only as a hash. This file is git-ignored; each machine
regenerates its own set by running this script.
"""
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.deps import get_conn                                    # noqa: E402
from app.seed import seed_company, create_department, mint_employee_token  # noqa: E402

DEPARTMENTS = ["Engineering", "Sales", "Compliance"]
TOKENS_PER_DEPT = 2
DEFAULT_OUT = Path(__file__).parent.parent / "DEMO-TOKENS.md"

# Demo telemetry shape. 30 days so both dashboard windows (7 and 30) have a
# curve rather than a straight line between two points.
SEED_DAYS = 30
SEED_RNG = 20260804  # fixed: the demo world is the same on every machine


def build_demo_world(company: str = "Acme Corp", out_path: Path = DEFAULT_OUT) -> dict:
    conn = get_conn()
    org_id, company_secret = seed_company(conn, company)
    depts = []
    for name in DEPARTMENTS:
        dept_id, dept_secret = create_department(conn, org_id, name)
        tokens = [mint_employee_token(conn, org_id, dept_id, name) for _ in range(TOKENS_PER_DEPT)]
        depts.append({"id": dept_id, "name": name, "secret": dept_secret, "tokens": tokens})

    from app.security import hash_token  # local import: keep module top clean
    NAMES = {
        "Engineering": ["Alice Tan", "Ben Lee"],
        "Sales": ["Carol Ng", "Devi Rao"],
        "Compliance": ["Ethan Ho", "Farah Idris"],
    }
    EVENTS = ["pii_block", "ethics_block", "warn_shown", "visit_unapproved", "request_sent"]
    EVENT_W = [3, 2, 5, 4, 3]   # blocks are rarer than warns and visits
    HOSTS = ["chatgpt.com", "claude.ai", "gemini.google.com", "copilot.microsoft.com"]
    HOST_W = [6, 4, 2, 1]
    rng = random.Random(SEED_RNG)
    now = datetime.now(timezone.utc)
    for d in depts:
        names = NAMES.get(d["name"], ["Sam Roe", "Kim Yeo"])
        for i, tok in enumerate(d["tokens"]):
            # label the token, then enrol a pseudonymous employee that inherits the name
            person = names[i % len(names)]
            conn.execute("UPDATE enroll_tokens SET name = ? WHERE token_hash = ?",
                         (person, hash_token(tok)))
            emp_id, pseudo = uuid.uuid4().hex, uuid.uuid4().hex
            conn.execute(
                "INSERT INTO employees (id, org_id, pseudo_id, department, department_id, name, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (emp_id, org_id, pseudo, d["name"], d["id"], person,
                 datetime.now(timezone.utc).isoformat()))
            # Spread events over SEED_DAYS with day-to-day variance, a quiet
            # weekend, and a mild upward trend, so the timelines have a shape.
            for day in range(SEED_DAYS):
                when = now - timedelta(days=day)
                weekend = when.weekday() >= 5
                trend = 1.0 + (SEED_DAYS - day) / SEED_DAYS      # busier lately
                mean = (0.5 if weekend else 1.8) * trend
                for _ in range(rng.randint(0, max(1, round(mean * 2)))):
                    ts = (when - timedelta(hours=rng.randrange(1, 23),
                                           minutes=rng.randrange(60))).isoformat()
                    etype = rng.choices(EVENTS, EVENT_W)[0]
                    host = rng.choices(HOSTS, HOST_W)[0]
                    conn.execute(
                        "INSERT INTO usage_events (id, org_id, employee_id, host, type, category, finding_hash, ts)"
                        " VALUES (?, ?, ?, ?, ?, ?, NULL, ?)",
                        (uuid.uuid4().hex, org_id, emp_id, host, etype,
                         "covert_surveillance" if etype == "ethics_block" else None, ts))
    conn.commit()

    lines = [
        f"# Demo credentials — {company}", "",
        "> **DEMO / TESTING ONLY.** Real deployments never write secrets to disk;",
        "> a secret is shown once and stored only as a hash. This file is",
        "> git-ignored and regenerated on each machine by `python scripts/seed.py`.",
        "", "## Company dashboard (role: **Company Admin**)",
        "- URL: http://localhost:8001/",
        f"- Org ID: `{org_id}`",
        f"- **Company Admin secret:** `{company_secret}`", "",
        "## Department dashboards (role: **Department Admin**)", "",
        "| Department | Department Admin secret |", "|---|---|",
    ]
    for d in depts:
        lines.append(f"| {d['name']} | `{d['secret']}` |")
    lines += ["", "## Employee tokens (paste into the extension)", ""]
    for d in depts:
        lines.append(f"### {d['name']}")
        for t in d["tokens"]:
            lines.append(f"- `{t}`")
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return {"org_id": org_id, "company_secret": company_secret, "departments": depts}


if __name__ == "__main__":
    summary = build_demo_world()
    print(f"org: Acme Corp ({summary['org_id']})")
    print(f"company secret: {summary['company_secret']}")
    for d in summary["departments"]:
        print(f"  {d['name']:<12} dept secret: {d['secret']}")
    print(f"\nAll secrets written to {DEFAULT_OUT}")
