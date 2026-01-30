from fastapi import APIRouter, Depends, HTTPException, Body, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload
from datetime import datetime
import secrets, string
from app.auth import get_current_user, require_permission
from app.database import get_db
from app.models import User
from app.auth import hash_password 
from ..ws_manager import manager
import asyncio
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from io import BytesIO
from app.models import User, Role

router = APIRouter(
    prefix="/api/users",
    tags=["Users"],
    dependencies=[Depends(get_current_user)]
)


# ------------------------------------------------------------
# 🔹 1. Alle Benutzer anzeigen (mit optionaler Ansicht für Gelöschte)
# ------------------------------------------------------------
@router.get("/", dependencies=[Depends(require_permission("user.manage"))])
def get_all_users(
    db: Session = Depends(get_db),
    # NEU: Query-Parameter, um gelöschte Benutzer einzuschließen
    show_deleted: bool = Query(False, description="Wenn True, werden auch gelöschte Benutzer (deleted=True) angezeigt.")
):
    """Gibt alle Benutzer (oder alle, inkl. gelöschter) mit Rollenname zurück"""
    
    query = db.query(User).options(joinedload(User.role))
    
    # NEU: Filterung basierend auf dem Parameter
    if not show_deleted:
        query = query.filter(User.deleted == False)

    users = query.all()

    result = []
    for u in users:
        result.append({
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "role_id": u.role_id,
            "role_name": u.role.name if u.role else None,
            "active": u.active,
            "deleted": u.deleted, # WICHTIG: deleted muss immer mitgegeben werden
            "must_change_password": u.must_change_password,
            "last_login": u.last_login.isoformat() if u.last_login else None,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        })
    return result

# ------------------------------------------------------------
# 🔹 2. Neuen Benutzer anlegen
# ------------------------------------------------------------
@router.post("/", dependencies=[Depends(require_permission("user.create"))])
async def create_user(
    data: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    username = data.get("username")
    email = data.get("email")
    role_id = data.get("role_id")
    active = data.get("active", True)

    if not username or not email:
        raise HTTPException(status_code=400, detail="Username und E-Mail sind Pflichtfelder")

    # Prüfen ob Benutzername schon existiert
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="Benutzername existiert bereits")

    # 🔐 Rolle sicher laden & prüfen
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=400, detail="Ungültige Rolle")
    
    from app.auth import assert_can_assign_role
    assert_can_assign_role(role, current_user)


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
# 🔹 3. Benutzerliste exportieren (ROBUSTES CSV mit UTF-8 BOM)
# ------------------------------------------------------------
@router.get("/export", dependencies=[Depends(require_permission("user.manage"))])
def export_users(db: Session = Depends(get_db)):
    today = datetime.now().strftime("%Y-%m-%d")

    filename = f"users_{today}.xlsx"
    

    # --- 1) Benutzer mit Rolle laden ---
    users = (
        db.query(User)
        .join(Role, User.role_id == Role.id, isouter=True)
        .all()
    )

    # --- 2) Excel-Datei erstellen ---
    wb = Workbook()
    ws = wb.active
    ws.title = "Users"

    # Kopfzeile
    headers = ["ID", "Benutzername", "Email", "Rolle", "Aktiv", "Erstellt am", "Gelöscht"]
    ws.append(headers)

    # --- 3) Jede Zeile ein User ---
    for u in users:
        ws.append([
            u.id,
            u.username,
            u.email,
            u.role.name if u.role else "—",
            "Ja" if u.active else "Nein",
            u.created_at.strftime("%d.%m.%Y %H:%M") if u.created_at else "",
            "Ja" if u.deleted else "Nein",
        ])

    # Optional: Spaltenbreiten automatisch anpassen
    for column_cells in ws.columns:
        length = max(len(str(cell.value)) for cell in column_cells)
        ws.column_dimensions[column_cells[0].column_letter].width = length + 2

    # --- 4) Datei in Bytes speichern ---
    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)

    # --- 5) Response zurückgeben ---
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )



# ------------------------------------------------------------
# 🔹 4 Benutzer bearbeiten
# ------------------------------------------------------------
@router.put("/{user_id}", dependencies=[Depends(require_permission("user.update"))])
async def update_user(
    user_id: int,
    data: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Wir erlauben keine Bearbeitung von gelöschten Benutzern über diesen Endpunkt
    user = db.query(User).filter(User.id == user_id, User.deleted == False).first()
    if not user:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden (oder gelöscht)")

    if "role_id" in data:

        # 🚫 Admin darf sich NICHT selbst downgraden
        if user.id == current_user.id:
            raise HTTPException(
                status_code=403,
                detail="Du kannst deine eigene Rolle nicht ändern"
            )

        # Rolle laden
        role = db.query(Role).filter(Role.id == data["role_id"]).first()
        if not role:
            raise HTTPException(status_code=400, detail="Ungültige Rolle")

        # 🔐 Admin-Rolle nur durch Admin vergebbar
        from app.auth import assert_can_assign_role
        assert_can_assign_role(role, current_user)

        # Rolle setzen
        user.role_id = role.id

    # Felder aktualisieren (aber kein Passwort)
    if "username" in data:
        user.username = data["username"]
    if "email" in data:
        user.email = data["email"]
    if "active" in data:
        user.active = data["active"]
    
    # Hier müsste die Optimistic Locking Logik stehen

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
# 🔹 4.1. Benutzer wiederherstellen (NEUE ROUTE)
# ------------------------------------------------------------
@router.put("/restore/{user_id}", dependencies=[Depends(require_permission("user.update"))])
async def restore_user(user_id: int, db: Session = Depends(get_db)):
    """Stellt einen zuvor gelöschten Benutzer wieder her (setzt deleted=False)."""
    # Benutzer suchen, auch wenn er deleted=True ist
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    
    if not user.deleted:
        return {"message": "Benutzer ist bereits aktiv."}

    user.deleted = False
    # Optional: user.active = True setzen, falls Wiederherstellung immer Aktivierung bedeutet
    db.commit()

    asyncio.create_task(manager.broadcast({
        "event": "user_updated", # Löst ein Frontend-Reload aus
        "id": user.id,
        "username": user.username,
        "role_id": user.role_id,
        "active": user.active
    }))

    return {"message": f"Benutzer {user.username} erfolgreich wiederhergestellt"}


# ------------------------------------------------------------
# 🔹 5. Passwort zurücksetzen (neues Einmalpasswort)
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
# 🔹 6. Benutzer löschen (Soft Delete)
# ------------------------------------------------------------
@router.delete("/{user_id}", dependencies=[Depends(require_permission("user.delete"))])
async def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")

    # ✅ ADMIN darf NICHT gelöscht werden
    if user.role and user.role.name.lower() == "admin":
        raise HTTPException(status_code=403, detail="Admin kann nicht gelöscht werden")
        
    if user.deleted:
        raise HTTPException(status_code=400, detail="Benutzer ist bereits gelöscht")

    user.deleted = True
    db.commit()

    asyncio.create_task(manager.broadcast({
        "event": "user_deleted",
        "id": user.id
    }))

    return {"message": "Benutzer gelöscht"}

# ------------------------------------------------------------
# 🔹 7. Daten einer User ID
# ------------------------------------------------------------

@router.get("/{user_id}", dependencies=[Depends(require_permission("user.update"))])
def get_user_by_id(user_id: int, db: Session = Depends(get_db)):
    # Sucht Benutzer, unabhängig vom deleted Status (wichtig für das Bearbeiten-Modal)
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role_id": user.role_id,
        "active": user.active,
        "deleted": user.deleted, # WICHTIG: deleted hier hinzufügen
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


# ------------------------------------------------------------
# 🔸 Hilfsfunktion: Einmalpasswort generieren
# ------------------------------------------------------------
def generate_temp_password(length: int = 10) -> str:
    alphabet = string.ascii_letters + string.digits
    return "OZS-" + "".join(secrets.choice(alphabet) for _ in range(length))