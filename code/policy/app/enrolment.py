"""Enrolment identity helpers.

The token is the durable identity. An employee row is a consequence of a
token, never an independent thing — which is what makes revocation able to
cascade and coverage able to be counted.
"""


def employee_for_token(conn, token_id: str) -> dict | None:
    """The employee this token already created, if any."""
    row = conn.execute(
        "SELECT id, pseudo_id FROM employees WHERE enroll_token_id = %s",
        (token_id,),
    ).fetchone()
    return dict(row) if row else None
