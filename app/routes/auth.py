from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime
from app.database import get_db
from app.models import User, Permission, RolePermission
from app.auth import create_access_token, verify_password, get_current_user, hash_password, oauth2_scheme
from pydantic import BaseModel, Field
from app.auth import SECRET_KEY, ALGORITHM      
from jose import jwt                            
from jose.exceptions import ExpiredSignatureError, JWTError 



router = APIRouter()

@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()

    if not user or user.deleted or not user.active:
        raise HTTPException(status_code=400, detail="Ungültiger Benutzer oder deaktiviert")

    if not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Falsches Passwort")

    if user.must_change_password is None or user.must_change_password is True:
        # Keine Weiterleitung, nur Info für Frontend
        return {
            "password_change_required": True,
            "username": user.username
        }
    
    # last_login aktualisieren
    user.last_login = datetime.utcnow()
    db.commit()

    token = create_access_token({"sub": user.username})

    role_permissions = [
        rp.permission.name
        for rp in user.role.permissions
    ]

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "username": user.username,
            "role_id": user.role_id,
            "must_change_password": bool(user.must_change_password),
            "active": user.active,
            "permissions": role_permissions,
        }
    }



@router.get("/me")
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    
    perms = (
        db.query(Permission.name)
        .join(RolePermission, Permission.id == RolePermission.permission_id)
        .filter(RolePermission.role_id == current_user.role_id)
        .all()
    )


    permission_list = [p[0] for p in perms]

    return {
        "id": current_user.id,
        "username": current_user.username,
        "role_id": current_user.role_id,
        "permissions": permission_list,
        "must_change_password": current_user.must_change_password,
        "active": current_user.active
    }


class PasswordChangeRequest(BaseModel):
    username: str = Field(..., example="admin")
    old_password: str = Field(..., example="admin")
    new_password: str = Field(..., example="Admin2025!")
    new_password_repeat: str = Field(..., example="Admin2025!")


@router.post("/change_password")
def change_password(
    data: PasswordChangeRequest,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == data.username).first()
    if not user:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")

    # Altes Passwort prüfen
    if not verify_password(data.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Das alte Passwort ist falsch")

    # Neue Passwörter vergleichen
    if data.new_password != data.new_password_repeat:
        raise HTTPException(status_code=400, detail="Die neuen Passwörter stimmen nicht überein")

    # Regeln
    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="Das Passwort muss mindestens 8 Zeichen haben")

    if data.new_password == data.old_password:
        raise HTTPException(status_code=400, detail="Das neue Passwort darf nicht dem alten entsprechen")

    # Neues Passwort setzen
    user.password_hash = hash_password(data.new_password)
    user.must_change_password = False
    user.last_login = datetime.utcnow()
    db.commit()

    return {"message": "Passwort erfolgreich geändert"}

@router.post("/refresh")
def refresh_token(token: str = Depends(oauth2_scheme)):
    try:
        # Token DEKODIEREN (ohne get_current_user, sonst blockiert expired tokens!)
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")

        if username is None:
            raise HTTPException(status_code=401, detail="Ungültiger Token")

    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token ist abgelaufen")
    except JWTError:
        raise HTTPException(status_code=401, detail="Ungültiger Token")

    # neuen Token erzeugen
    new_token = create_access_token({"sub": username})

    return {"access_token": new_token}
