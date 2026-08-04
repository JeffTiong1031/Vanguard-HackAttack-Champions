"""Seed data: the curated AI-tool registry and a demo org.

The registry is deliberately a short, explicit list. It is why the extension
asks for eight host permissions instead of <all_urls> -- doc 02 section 6.4's
un-N/A-able security-questionnaire row.
"""
import uuid

from app.security import hash_password, new_token, now_iso

# (id, host, display_name)
REGISTRY: list[tuple[str, str, str]] = [
    ("openai",     "chatgpt.com",           "ChatGPT"),
    ("anthropic",  "claude.ai",             "Claude"),
    ("google",     "gemini.google.com",     "Google Gemini"),
    ("microsoft",  "copilot.microsoft.com", "Microsoft Copilot"),
    ("perplexity", "www.perplexity.ai",     "Perplexity"),
    ("deepseek",   "chat.deepseek.com",     "DeepSeek"),
    ("mistral",    "chat.mistral.ai",       "Le Chat (Mistral)"),
    ("xai",        "grok.com",              "Grok"),
]

# (key, label). The first two are the case study's own named prohibitions.
ETHICS_CATEGORIES: list[tuple[str, str]] = [
    ("covert_surveillance",      "Covert monitoring of employees"),
    ("undisclosed_profiling",    "Profiling people without their knowledge"),
    ("discriminatory_screening", "Screening or ranking people on protected attributes"),
    ("security_evasion",         "Evading security controls or producing exploit code"),
    ("harassment_content",       "Harassing, threatening, or abusive content"),
    ("regulatory_circumvention", "Circumventing legal or regulatory obligations"),
]

_DEFAULT_APPROVED = {"openai", "anthropic"}


def seed_registry(conn) -> None:
    conn.executemany(
        "INSERT INTO llm_registry (id, host, display_name) VALUES (%s, %s, %s)"
        " ON CONFLICT DO NOTHING",
        REGISTRY,
    )
    conn.commit()


def seed_demo_org(conn, name: str, admin_password: str) -> str:
    org_id = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO orgs (id, name, admin_password_hash, policy_version)"
        " VALUES (%s, %s, %s, 1)",
        (org_id, name, hash_password(admin_password)),
    )
    conn.executemany(
        "INSERT INTO org_llm_policy (org_id, llm_id, status) VALUES (%s, %s, %s)",
        [
            (org_id, llm_id, "approved" if llm_id in _DEFAULT_APPROVED else "blocked")
            for llm_id, _, _ in REGISTRY
        ],
    )
    conn.executemany(
        "INSERT INTO policy_category (org_id, key, label, enabled) VALUES (%s, %s, %s, 1)",
        [(org_id, key, label) for key, label in ETHICS_CATEGORIES],
    )
    conn.commit()
    return org_id


def seed_org_policy(conn, org_id: str) -> None:
    """Insert the default org_llm_policy + policy_category rows for a company.

    Shared by seed_demo_org's password-era path and seed_company's
    generated-secret path below, so the default tool/category posture is
    defined in exactly one place.
    """
    conn.executemany(
        "INSERT INTO org_llm_policy (org_id, llm_id, status) VALUES (%s, %s, %s)"
        " ON CONFLICT DO NOTHING",
        [(org_id, llm_id, "approved" if llm_id in _DEFAULT_APPROVED else "blocked")
         for llm_id, _, _ in REGISTRY],
    )
    conn.executemany(
        "INSERT INTO policy_category (org_id, key, label, enabled) VALUES (%s, %s, %s, 1)"
        " ON CONFLICT DO NOTHING",
        [(org_id, key, label) for key, label in ETHICS_CATEGORIES],
    )
    conn.commit()


def seed_company(conn, name: str) -> tuple[str, str]:
    """Create a company and return (org_id, admin_secret_plaintext).

    The company's console secret is a generated high-entropy token, hashed
    with SHA-256 (app/security.hash_token via new_token) -- not scrypt: it is
    generated, not human-chosen, so the plaintext is shown here once and
    never stored. `admin_password_hash` is left '' -- self-signup companies
    have no password-era credential.
    """
    org_id = uuid.uuid4().hex
    plain, hashed = new_token("VG")
    conn.execute(
        "INSERT INTO orgs (id, name, admin_password_hash, admin_token_hash, policy_version)"
        " VALUES (%s, %s, '', %s, 1)",
        (org_id, name, hashed),
    )
    seed_org_policy(conn, org_id)
    return org_id, plain


def create_department(conn, org_id: str, name: str) -> tuple[str, str]:
    """Create a department under org_id and return (department_id, admin_secret_plaintext)."""
    dept_id = uuid.uuid4().hex
    plain, hashed = new_token(name[:3])
    conn.execute(
        "INSERT INTO departments (id, org_id, name, admin_token_hash, created_at)"
        " VALUES (%s, %s, %s, %s, %s)",
        (dept_id, org_id, name, hashed, now_iso()),
    )
    conn.commit()
    return dept_id, plain


def mint_employee_token(
    conn, org_id: str, department_id: str, department_name: str,
) -> str:
    """Mint an employee enrolment token scoped to one department. Returns the
    plaintext -- shown once, stored only as a hash."""
    plain, hashed = new_token(department_name[:3])
    conn.execute(
        "INSERT INTO enroll_tokens (id, org_id, department, department_id, token_hash, label, created_at)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (uuid.uuid4().hex, org_id, department_name, department_id, hashed, department_name, now_iso()),
    )
    conn.commit()
    return plain
