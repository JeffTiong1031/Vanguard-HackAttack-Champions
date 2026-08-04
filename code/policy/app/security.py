"""Hashing and sessions.

Two hashing strategies, deliberately:

  * Enrolment tokens are 160 bits of `secrets` randomness. There is nothing to
    guess, so a fast SHA-256 is correct.
  * The admin password is low-entropy and human-chosen. A fast hash there is
    brute-forced offline, so it gets scrypt. ADR 0009 records this exact error
    being made once already, against codename dictionaries.
"""
import hashlib
import secrets
from datetime import datetime, timezone


_SCRYPT_N = 2 ** 14
_SCRYPT_R = 8
_SCRYPT_P = 1


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_token(prefix: str) -> tuple[str, str]:
    """Return (plaintext, hash). The plaintext is shown once and never stored."""
    plain = f"{prefix.upper()}-{secrets.token_urlsafe(20)}"
    return plain, hash_token(plain)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(pw.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
    return f"scrypt${salt.hex()}${dk.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        scheme, salt_hex, want_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        got = hashlib.scrypt(
            pw.encode(), salt=bytes.fromhex(salt_hex),
            n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P,
        )
        return secrets.compare_digest(got.hex(), want_hex)
    except (ValueError, AttributeError):
        return False


def issue_session(
    conn, org_id: str, role: str = "company",
    department_id: str | None = None,
) -> str:
    token = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO admin_sessions (token, org_id, role, department_id, created_at)"
        " VALUES (%s, %s, %s, %s, %s)",
        (token, org_id, role, department_id, now_iso()),
    )
    conn.commit()
    return token


def session_org(conn, token: str | None) -> str | None:
    if not token:
        return None
    row = conn.execute(
        "SELECT org_id FROM admin_sessions WHERE token = %s", (token,)
    ).fetchone()
    return row["org_id"] if row else None


def resolve_session(conn, token: str | None):
    """Full session row (org_id, role, department_id) for a role-scoped guard.

    `session_org` above is kept, unchanged, for the pre-hierarchy call sites
    that only ever need an org_id -- it still works because `role` now defaults
    to 'company' and every legacy session row is a company session in spirit.
    """
    if not token:
        return None
    return conn.execute(
        "SELECT org_id, role, department_id FROM admin_sessions WHERE token = %s",
        (token,),
    ).fetchone()
