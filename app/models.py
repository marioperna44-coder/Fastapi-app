from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Beziehung: eine Rolle hat viele Benutzer
    users = relationship("User", back_populates="role")
    permissions = relationship("RolePermission", back_populates="role")

class Permission(Base):
    __tablename__ = "permissions"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    roles = relationship("RolePermission", back_populates="permission")

class RolePermission(Base):
    __tablename__ = "role_permissions"
    id = Column(Integer, primary_key=True, index=True)
    role_id = Column(Integer, ForeignKey("roles.id"))
    permission_id = Column(Integer, ForeignKey("permissions.id"))
    assigned_at = Column(DateTime, default=datetime.utcnow)

    role = relationship("Role", back_populates="permissions")
    permission = relationship("Permission", back_populates="roles")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    email = Column(String)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)
    role_id = Column(Integer, ForeignKey("roles.id"))
    must_change_password = Column(Boolean, default=False)
    deleted = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    role = relationship("Role", back_populates="users")


class Pulver(Base):
    __tablename__ = "pulver"

    id = Column(Integer, primary_key=True, index=True)
    barcode = Column(String, unique=True, nullable=False)  # z. B. OZS-00001
    artikelnummer = Column(String, unique=True, nullable=False)
    hersteller = Column(String, nullable=True)
    farbe = Column(String, nullable=True)
    qualitaet = Column(String, nullable=True)
    oberflaeche = Column(String, nullable=True)
    anwendung = Column(String, nullable=True)
    menge_kg = Column(Float, default=0.0)
    start_menge_kg = Column(Float, nullable=False)
    lagerort = Column(String, nullable=True)
    aktiv = Column(Boolean, default=True)
    deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Beziehungen
    creator = relationship("User", back_populates="pulver_created")
    bewegungen = relationship("PulverBewegung", back_populates="pulver")


class PulverBewegung(Base):
    __tablename__ = "pulver_bewegung"

    id = Column(Integer, primary_key=True, index=True)
    pulver_id = Column(Integer, ForeignKey("pulver.id"), nullable=False)
    barcode = Column(String, nullable=False)  # eindeutiger Karton
    datum = Column(DateTime, default=datetime.utcnow)
    menge_alt = Column(Float, nullable=False)  # Bestand vor der Änderung
    menge_neu = Column(Float, nullable=False)  # Bestand nach der Änderung
    beschreibung = Column(String, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Beziehungen
    pulver = relationship("Pulver", back_populates="bewegungen")
    user = relationship("User")


User.pulver_created = relationship("Pulver", back_populates="creator")

class Lock(Base):
    __tablename__ = "locks"

    id = Column(Integer, primary_key=True, index=True)
    area = Column(String, nullable=False)         # z. B. "pulver" | "users" | "roles"
    object_id = Column(Integer, nullable=False)   # ID der Ressource
    locked_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    locked_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", backref="locks")