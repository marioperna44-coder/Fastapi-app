# app/routes/locks.py

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.database import get_db
from app.auth import get_current_user
from app.models import Lock, User

# Wichtig: wir importieren den WebSocket-Broadcast aus main.py
from app.main import notify_lock_update


router = APIRouter(
    prefix="/api/locks",
    tags=["Locks"],
    dependencies=[Depends(get_current_user)]
)


LOCK_TTL_MINUTES = 5


# ------------------------------------------------------------
# 🔹 Lock anfordern
# ------------------------------------------------------------
@router.post("/acquire")
def acquire_lock(
    resource: str = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    now = datetime.utcnow()
    ttl = timedelta(minutes=LOCK_TTL_MINUTES)

    # Abgelaufene Locks löschen
    db.query(Lock).filter(Lock.expires_at < now).delete()

    # Prüfen, ob bereits ein Lock existiert
    existing = db.query(Lock).filter(Lock.resource == resource).first()

    if existing:
        if existing.locked_by == current_user.id:
            # eigenes Lock verlängern
            existing.expires_at = now + ttl
            db.commit()
            return {"status": "extended"}
        else:
            # jemand anderes hält das Lock
            return {
                "status": "locked",
                "locked_by": existing.locked_by,
                "expires_at": existing.expires_at.isoformat()
            }

    # Neues Lock setzen
    lock = Lock(
        resource=resource,
        locked_by=current_user.id,
        locked_at=now,
        expires_at=now + ttl
    )
    db.add(lock)
    db.commit()

    # WebSocket-Broadcast
    notify_lock_update(resource, action="locked", user_id=current_user.id)

    return {"status": "acquired"}


# ------------------------------------------------------------
# 🔹 Lock freigeben
# ------------------------------------------------------------
@router.post("/release")
def release_lock(
    resource: str = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    lock = db.query(Lock).filter(
        Lock.resource == resource,
        Lock.locked_by == current_user.id
    ).first()

    if not lock:
        return {"status": "not_locked"}

    db.delete(lock)
    db.commit()

    # WebSocket-Broadcast
    notify_lock_update(resource, action="unlocked", user_id=current_user.id)

    return {"status": "released"}


# ------------------------------------------------------------
# 🔹 Heartbeat (optional)
# ------------------------------------------------------------
@router.post("/heartbeat")
def lock_heartbeat(
    resource: str = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    lock = db.query(Lock).filter(
        Lock.resource == resource,
        Lock.locked_by == current_user.id
    ).first()

    if not lock:
        return {"status": "missing"}

    lock.expires_at = datetime.utcnow() + timedelta(minutes=LOCK_TTL_MINUTES)
    db.commit()

    return {"status": "extended"}
