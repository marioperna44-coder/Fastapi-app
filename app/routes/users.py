from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session, joinedload
from datetime import datetime
import secrets, string
from app.auth import get_current_user, require_permission
from app.database import get_db
from app.models import User
from app.auth import hash_password   # bereits vorhanden aus deiner auth.py
from ..ws_manager import manager
import asyncio


router = APIRouter(
    prefix="/api/users",
    tags=["Users"],
    dependencies=[Depends(get_current_user)]
)


# ------------------------------------------------------------
# 🔹 1. Alle Benutzer anzeigen (ohne Passwort)
# ------------------------------------------------------------
@router.get("/", dependencies=[Depends(require_permission("user.manage"))])
def get_all_users(db: Session = Depends(get_db)):
    """Gibt alle Benutzer mit Rollenname zurück"""
    users = (
    db.query(User)
    .options(joinedload(User.role))
    .filter(User.deleted == False)
    .all()
    )

    result = []
    for u in users:
        result.append({
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "role_id": u.role_id,
            "role_name": u.role.name if u.role else None,
            "active": u.active,
            "deleted": u.deleted,
            "must_change_password": u.must_change_password,
            "last_login": u.last_login,
            "created_at": u.created_at
        })
    return result

# ------------------------------------------------------------
# 🔹 2. Neuen Benutzer anlegen
# ------------------------------------------------------------
@router.post("/", dependencies=[Depends(require_permission("user.create"))])
async def create_user(data: dict = Body(...), db: Session = Depends(get_db)):
    username = data.get("username")
    email = data.get("email")
    role_id = data.get("role_id")
    active = data.get("active", True)

    if not username or not email:
        raise HTTPException(status_code=400, detail="Username und E-Mail sind Pflichtfelder")

    # Prüfen ob Benutzername schon existiert
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="Benutzername existiert bereits")

    # Einmalpasswort generieren
    temp_pw = generate_temp_password()
    password_hash = hash_password(temp_pw)

    new_user = User(
        username=username,
        email=email,
        role_id=role_id,
        active=active,
        deleted=False,
        must_change_password=True,
        password_hash=password_hash,
        created_at=datetime.utcnow(),
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    asyncio.create_task(manager.broadcast({
        "event": "user_created",
        "id": new_user.id,
        "username": new_user.username,
        "role_id": new_user.role_id,
    }))

    return {
        "message": "Benutzer erfolgreich angelegt",
        "user": {
            "id": new_user.id,
            "username": new_user.username,
            "email": new_user.email,
            "role_id": new_user.role_id,
            "active": new_user.active,
        },
        "temp_password": temp_pw,
    }


# ------------------------------------------------------------
# 🔹 3. Benutzer bearbeiten (ohne Passwort)
# ------------------------------------------------------------
@router.put("/{user_id}", dependencies=[Depends(require_permission("user.update"))])
async def update_user(user_id: int, data: dict, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id, User.deleted == False).first()
    if not user:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")

    # ✅ ADMIN darf nicht bearbeitet werden
    if user.role and user.role.name.lower() == "admin":
        raise HTTPException(status_code=403, detail="Admin kann nicht bearbeitet werden")

    # Felder aktualisieren (aber kein Passwort)
    if "username" in data:
        user.username = data["username"]
    if "email" in data:
        user.email = data["email"]
    if "role_id" in data:
        user.role_id = data["role_id"]
    if "active" in data:
        user.active = data["active"]

    db.commit()

    asyncio.create_task(manager.broadcast({
        "event": "user_updated",
        "id": user.id,
        "username": user.username,
        "role_id": user.role_id,
        "active": user.active
    }))

    return {"message": "Benutzerdaten aktualisiert"}



# ------------------------------------------------------------
# 🔹 4. Passwort zurücksetzen (neues Einmalpasswort)
# ------------------------------------------------------------
@router.post("/{user_id}/reset_password", dependencies=[Depends(require_permission("user.update"))])
def reset_password(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id, User.deleted == False).first()
    if not user:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")

    temp_pw = generate_temp_password()
    user.password_hash = hash_password(temp_pw)
    user.must_change_password = True
    db.commit()

    return {
        "message": "Einmalpasswort vergeben",
        "username": user.username,
        "temp_password": temp_pw,
    }


# ------------------------------------------------------------
# 🔹 5. Benutzer löschen (Soft Delete)
# ------------------------------------------------------------
@router.delete("/{user_id}", dependencies=[Depends(require_permission("user.delete"))])
async def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")

    # ✅ ADMIN darf NICHT gelöscht werden
    if user.role and user.role.name.lower() == "admin":
        raise HTTPException(status_code=403, detail="Admin kann nicht gelöscht werden")

    user.deleted = True
    db.commit()

    asyncio.create_task(manager.broadcast({
        "event": "user_deleted",
        "id": user.id
    }))

    return {"message": "Benutzer gelöscht"}

# ------------------------------------------------------------
# 🔹 6. Daten einer User ID
# ------------------------------------------------------------

@router.get("/{user_id}", dependencies=[Depends(require_permission("user.update"))])
def get_user_by_id(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id, User.deleted == False).first()

    if not user:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role_id": user.role_id,
        "active": user.active,
        "last_login": user.last_login,
        "created_at": user.created_at,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }

# ------------------------------------------------------------
# 🔸 Hilfsfunktion: Einmalpasswort generieren
# ------------------------------------------------------------
def generate_temp_password(length: int = 10) -> str:
    alphabet = string.ascii_letters + string.digits
    return "OZS-" + "".join(secrets.choice(alphabet) for _ in range(length))