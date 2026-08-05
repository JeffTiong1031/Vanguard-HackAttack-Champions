"""Enrolment identity helpers.

The token is the durable identity. An employee row is a consequence of a
token, never an independent thing — which is what makes revocation able to
cascade and coverage able to be counted.
"""
from datetime import datetime, timedelta


def employee_for_token(conn, token_id: str) -> dict | None:
    """The employee this token already created, if any."""
    row = conn.execute(
        "SELECT id, pseudo_id FROM employees WHERE enroll_token_id = %s",
        (token_id,),
    ).fetchone()
    return dict(row) if row else None


UNUSED_TOKEN_TTL = timedelta(days=7)


def token_is_expired(created_at: str, now: datetime, used: bool) -> bool:
    """Expiry applies to CLAIMING a token, never to keeping it.

    Once a token has created an employee it is that person's permanent
    identity, so a reinstall a year later still resolves. Only a token
    nobody ever used goes stale — which is the leaked-email case.

    `created_at` is `enroll_tokens.created_at`, always written by
    `now_iso()` (`datetime.now(timezone.utc).isoformat()`), so it always
    parses to a timezone-aware datetime here. `now` must be passed
    timezone-aware too (the call site uses `datetime.now(timezone.utc)`) --
    a naive `created_at` would raise TypeError on comparison rather than
    silently comparing wrong, which is preferable to guessing a timezone.
    """
    if used:
        return False
    return datetime.fromisoformat(created_at) + UNUSED_TOKEN_TTL < now
