from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from app.ws_manager import manager
import asyncio

from app.database import get_db
from app.auth import get_current_user, require_permission
from app.models import Role, RolePermission, Permission

router = APIRouter(
    prefix="/api/roles",
    tags=["Roles"],
    dependencies=[Depends(get_current_user)]
)

# ------------------------------------------------------------
# 🔹 Neue Rolle anlegen
# ------------------------------------------------------------

@router.post("/", dependencies=[Depends(require_permission("new.role"))])
async def create_role(
    data: dict = Body(...),
    db: Session = Depends(get_db)
):
    """
    Neue Rolle anlegen
    """
    name = data.get("name")
    description = data.get("description")

    # Pflichtfeld prüfen
    if not name:
        raise HTTPException(status_code=400, detail="Rollenname ist ein Pflichtfeld")

    # prüfen ob Rolle existiert
    existing = db.query(Role).filter(Role.name == name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Rolle '{name}' existiert bereits")

    # neue Rolle erstellen
    new_role = Role(
        name=name,
        description=description,
        created_at=datetime.utcnow()
    )

    try:
        db.add(new_role)
        db.commit()
        db.refresh(new_role)

        # 🔥 WebSocket Event senden
        asyncio.create_task(manager.broadcast({
            "event": "role_created",
            "id": new_role.id,
            "name": new_role.name
        }))

    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Fehler: Rolleneintrag bereits vorhanden")

    return {
        "message": "Rolle erfolgreich angelegt",
        "role": {
            "id": new_role.id,
            "name": new_role.name,
            "description": new_role.description,
            "created_at": new_role.created_at
        }
    }

# ------------------------------------------------------------
# 🔹 Permission zuweisen
# ------------------------------------------------------------

@router.post("/assign_permissions", dependencies=[Depends(require_permission("manage.permission"))])
async def assign_permissions(
    data: dict = Body(...),
    db: Session = Depends(get_db)
):
    """
    Setzt die Berechtigungen einer Rolle mit Optimistic Locking.
    Erwartet:
    {
        "role_id": 2,
        "permission_ids": [1,2,3],
        "updated_at": "2025-11-25T10:15:00"
    }
    """

    role_id = data.get("role_id")
    client_updated_at = data.get("updated_at")
    permission_ids = data.get("permission_ids", [])

    if not role_id:
        raise HTTPException(status_code=400, detail="role_id fehlt")

    if not isinstance(permission_ids, list):
        raise HTTPException(status_code=400, detail="permission_ids muss eine Liste sein")

    # Rolle existiert?
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Rolle nicht gefunden")

    # Admin darf nicht geändert werden
    if role.name.lower() == "admin":
        raise HTTPException(status_code=403, detail="Admin-Rechte können nicht verändert werden")

    # OPTIMISTIC LOCKING
    if client_updated_at:
        client_dt = datetime.fromisoformat(client_updated_at)
        if role.updated_at != client_dt:
            raise HTTPException(
                status_code=409,
                detail="Diese Rolle wurde inzwischen von einem anderen Benutzer geändert. Bitte neu laden."
            )

    # Permissions validieren
    valid_ids = set(
        pid for (pid,) in db.query(Permission.id)
        .filter(Permission.id.in_(permission_ids))
        .all()
    )

    if len(valid_ids) != len(permission_ids):
        raise HTTPException(status_code=400, detail="Eine oder mehrere permission_ids sind ungültig")

    # Alte Rechte löschen
    db.query(RolePermission).filter(RolePermission.role_id == role_id).delete()

    # Neue Rechte setzen
    for pid in valid_ids:
        db.add(RolePermission(role_id=role_id, permission_id=pid))

    # updated_at aktualisieren
    role.updated_at = datetime.utcnow()
    db.commit()

    # 🔥 WEBSOCKET EVENT SENDEN
    asyncio.create_task(manager.broadcast({
        "event": "role_updated",
        "role_id": role_id
    }))

    return {
        "message": "Rollenrechte aktualisiert",
        "role_id": role_id,
        "updated_at": role.updated_at,
        "assigned_permissions": list(valid_ids)
    }

# ------------------------------------------------------------
# 🔹 Permission anlegen
# ------------------------------------------------------------
@router.post("/permissions/")
def create_permission(
    data: dict = Body(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Fügt eine neue Berechtigung hinzu und weist sie automatisch der Admin-Rolle zu.
    """
    name = data.get("name")
    description = data.get("description", "")

    if not name:
        raise HTTPException(status_code=400, detail="Name der Permission ist Pflichtfeld")

    # prüfen ob Permission existiert
    existing = db.query(Permission).filter(Permission.name == name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Permission existiert bereits")

    new_perm = Permission(
        name=name,
        description=description,
        created_at=datetime.utcnow()
    )

    try:
        db.add(new_perm)
        db.commit()
        db.refresh(new_perm)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Fehler beim Erstellen der Permission")

    # 🔥 ADMIN automatisch diese Permission geben
    admin_role = db.query(Role).filter(Role.name.ilike("admin")).first()
    if admin_role:
        rp = RolePermission(
            role_id=admin_role.id,
            permission_id=new_perm.id,
            assigned_at=datetime.utcnow()
        )
        db.add(rp)
        db.commit()

    return {
        "message": "Permission erfolgreich angelegt",
        "permission": {
            "id": new_perm.id,
            "name": new_perm.name,
            "description": new_perm.description
        },
        "admin_assigned": True
    }

# ------------------------------------------------------------
# 🔹 Permission einholen 
# ------------------------------------------------------------

@router.get("/permissions", dependencies=[Depends(require_permission("roles.manage"))])
def get_permissions(db: Session = Depends(get_db)):
    perms = db.query(Permission).all()

    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description
        }
        for p in perms
    ]

@router.get("/roles", dependencies=[Depends(require_permission("roles.manage"))])
def get_roles(db: Session = Depends(get_db)):
    roles = db.query(Role).all()

    return [
        {
            "id": r.id,
            "name": r.name,
            "description": r.description
        }
        for r in roles
    ]

@router.get("/roles/{role_id}/permissions", dependencies=[Depends(require_permission("manage.permission"))])
def get_role_permissions(role_id: int, db: Session = Depends(get_db)):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Rolle nicht gefunden")

    permission_ids = [rp.permission_id for rp in role.permissions]

    return {
        "role_id": role.id,
        "role_name": role.name,
        "permissions": permission_ids,
        "updated_at": role.updated_at.isoformat()  # 🔥 WICHTIG!
    }