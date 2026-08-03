"""Build the demo world and record every secret/token in DEMO-TOKENS.md.

Run before a demo:  python scripts/seed.py

DEMO / TESTING ONLY. Real deployments never write secrets to disk -- a secret
is shown once and stored only as a hash. This file is git-ignored; each machine
regenerates its own set by running this script.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.deps import get_conn                                    # noqa: E402
from app.seed import seed_company, create_department, mint_employee_token  # noqa: E402

DEPARTMENTS = ["Engineering", "Sales", "Compliance"]
TOKENS_PER_DEPT = 2
DEFAULT_OUT = Path(__file__).parent.parent / "DEMO-TOKENS.md"


def build_demo_world(company: str = "Acme Corp", out_path: Path = DEFAULT_OUT) -> dict:
    conn = get_conn()
    org_id, company_secret = seed_company(conn, company)
    depts = []
    for name in DEPARTMENTS:
        dept_id, dept_secret = create_department(conn, org_id, name)
        tokens = [mint_employee_token(conn, org_id, dept_id, name) for _ in range(TOKENS_PER_DEPT)]
        depts.append({"id": dept_id, "name": name, "secret": dept_secret, "tokens": tokens})

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
