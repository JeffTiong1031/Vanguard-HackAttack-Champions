"""Employee notification routes and automated alert dispatching."""
import logging
import uuid

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.deps import get_conn
from app.security import now_iso

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/notifications")


class MarkReadRequest(BaseModel):
    pseudo_id: str
    notification_ids: list[str] = []


def create_notification(conn, org_id: str, employee_id: str, kind: str, title: str, message: str) -> str:
    """Create in-app notification record and trigger automated email alert dispatch."""
    notif_id = uuid.uuid4().hex
    now = now_iso()
    
    conn.execute(
        "INSERT INTO notifications (id, org_id, employee_id, kind, title, message, status, created_at)"
        " VALUES (%s, %s, %s, %s, %s, %s, 'unread', %s)",
        (notif_id, org_id, employee_id, kind, title, message, now),
    )

    # Fetch employee pseudo_id for simulated email dispatch
    emp = conn.execute(
        "SELECT pseudo_id FROM employees WHERE id = %s", (employee_id,)
    ).fetchone()
    
    emp_email = f"employee-{employee_id[:8]}@company.internal"
    
    # Automated Email Alert Dispatch Simulation
    logger.info("[EMAIL DISPATCHED] To: %s | Subject: %s | Body: %s", emp_email, title, message)
    print(f"\n📩 [EMAIL NOTIFICATION DISPATCHED]\n  To: {emp_email}\n  Subject: {title}\n  Message: {message}\n")

    return notif_id


@router.get("")
async def list_notifications(pseudo_id: str = Query(...)) -> list[dict]:
    """Fetch all unread and recent notifications for the enrolled employee."""
    conn = get_conn()
    emp = conn.execute(
        "SELECT id FROM employees WHERE pseudo_id = %s", (pseudo_id,)
    ).fetchone()
    if emp is None:
        raise HTTPException(status_code=401, detail="unknown enrolment")

    rows = conn.execute(
        "SELECT id, kind, title, message, status, created_at"
        " FROM notifications WHERE employee_id = %s ORDER BY created_at DESC LIMIT 50",
        (emp["id"],),
    ).fetchall()

    return [dict(r) for r in rows]


@router.post("/mark-read")
async def mark_notifications_read(body: MarkReadRequest) -> dict[str, str]:
    """Mark specified or all notifications as read."""
    conn = get_conn()
    emp = conn.execute(
        "SELECT id FROM employees WHERE pseudo_id = %s", (body.pseudo_id,)
    ).fetchone()
    if emp is None:
        raise HTTPException(status_code=401, detail="unknown enrolment")

    if body.notification_ids:
        for nid in body.notification_ids:
            conn.execute(
                "UPDATE notifications SET status = 'read' WHERE id = %s AND employee_id = %s",
                (nid, emp["id"]),
            )
    else:
        conn.execute(
            "UPDATE notifications SET status = 'read' WHERE employee_id = %s",
            (emp["id"],),
        )

    conn.commit()
    return {"status": "ok"}
