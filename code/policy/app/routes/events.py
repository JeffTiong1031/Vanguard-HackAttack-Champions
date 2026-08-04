"""Governance event ingestion.

🔴 I3. `UsageEvent` has no field for prompt text and sets extra="forbid", so a
client attempting to send one receives a 422 instead of having the field
quietly dropped. The rejection is the point: silent tolerance is how a field
becomes a column.
"""
import logging
import uuid

from fastapi import APIRouter, HTTPException

from app.deps import get_conn
from app.models import EventBatch

log = logging.getLogger("vanguard.policy")
router = APIRouter()


@router.post("/v1/events", status_code=202)
async def ingest(batch: EventBatch) -> dict[str, int]:
    conn = get_conn()
    row = conn.execute(
        "SELECT id, org_id FROM employees WHERE pseudo_id = %s", (batch.pseudo_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=401, detail="unknown enrolment")

    conn.executemany(
        "INSERT INTO usage_events"
        " (id, org_id, employee_id, host, type, category, finding_hash, ts)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        [
            (uuid.uuid4().hex, row["org_id"], row["id"], e.host, e.type,
             e.category, e.finding_hash, e.ts)
            for e in batch.events
        ],
    )
    conn.commit()
    # Count only. Never the host, never the category, never the hash.
    log.info("ingested events n=%d", len(batch.events))
    return {"accepted": len(batch.events)}
