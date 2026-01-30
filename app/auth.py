from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.hash import pbkdf2_sha256
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, RolePermission, Permission, Role
from jose.exceptions import ExpiredSignatureError

# Geheimschlüssel für JWT
SECRET_KEY = "mein-geheimer-schluessel"  # später aus .env laden!
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 # 8 Stunden gültig
ADMIN_ROLE_NAME = "admin"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")


# ----------------------------------------------------
# Token-Helferfunktionen
# ----------------------------------------------------
def create_access_token(data: dict, expires_delta: timedelta = None):
    """JWT Token erzeugen"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_password(plain_password, hashed_password):
    return pbkdf2_sha256.verify(plain_password, hashed_password)


def hash_password(password):
    return pbkdf2_sha256.hash(password)


# ----------------------------------------------------
# Benutzer abrufen aus Token
# ----------------------------------------------------
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Aktuellen Benutzer anhand Token laden"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Ungültige Anmeldedaten",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token abgelaufen. Bitte erneut anmelden.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()
    if user is None or user.deleted or not user.active:
        raise credentials_exception
    return user

def require_permission(permission_name: str):
    """Prüft, ob der aktuelle User die angegebene Permission besitzt."""

    def dependency(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):

        # 1. Rolle holen
        role_id = current_user.role_id

        # 2. Alle Permission-Einträge dieser Rolle holen
        perms = (
            db.query(Permission.name)
            .join(RolePermission, Permission.id == RolePermission.permission_id)
            .filter(RolePermission.role_id == role_id)
            .all()
        )

        # Ergebnis ist Liste von Tupeln → normalisieren
        user_permissions = [p[0] for p in perms]

        # 3. Prüfen
        if permission_name not in user_permissions:
            raise HTTPException(
                status_code=403,
                detail=f"Fehlende Berechtigung: {permission_name}"
            )

        # 4. OK → Zugriff gewähren
        return current_user

    return dependency

def assert_can_assign_role(target_role: Role, current_user: User):
    if target_role.name.lower() == ADMIN_ROLE_NAME:
        if not current_user.role or current_user.role.name.lower() != ADMIN_ROLE_NAME:
            raise HTTPException(
                status_code=403,
                detail="Nur Admins dürfen Admin-Rollen vergeben"
            )