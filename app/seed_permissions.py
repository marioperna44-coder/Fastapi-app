# app/seed_permissions.py

from app.database import SessionLocal
from app.models import Role, User, Permission, RolePermission
from app.auth import hash_password
from datetime import datetime


PERMISSIONS = [
    # Rollen & Rechte
    ("roles.manage", "Seite Rollen & Rechte öffnen"),
    ("new.role", "Neue Rolle anlegen"),
    ("manage.permission", "Rechte einer Rolle verwalten"),

    # Benutzerverwaltung
    ("user.manage", "Benutzerverwaltung öffnen"),
    ("user.create", "Benutzer anlegen"),
    ("user.update", "Benutzer bearbeiten"),
    ("user.delete", "Benutzer löschen"),

    # Pulverlager
    ("pulver.manage", "Pulverlager öffnen"),
    ("powder.create", "Pulver anlegen"),
    ("powder.update", "Pulver bearbeiten"),
    ("powder.label", "Pulverlabel drucken"),
    ("pulver.track", "Pulverbewegung erfassen"),

    # Auftragsdisplay
    ("auftraege.manage", "Auftragsdisplay öffnen"),
]


def run_seed():
    db = SessionLocal()

    print("🔄 Starte Seeding...")

    # -----------------------------------------------------
    # 1) ADMIN ROLE
    # -----------------------------------------------------
    admin_role = db.query(Role).filter(Role.name == "Admin").first()
    if not admin_role:
        admin_role = Role(
            name="Admin",
            description="Systemadministrator (volle Rechte)",
            created_at=datetime.utcnow()
        )
        db.add(admin_role)
        db.commit()
        db.refresh(admin_role)
        print("✔ Admin-Rolle angelegt.")
    else:
        print("ℹ Admin-Rolle existiert bereits.")

    # -----------------------------------------------------
    # 2) PERMISSIONS
    # -----------------------------------------------------
    created_permissions = []
    for name, desc in PERMISSIONS:
        perm = db.query(Permission).filter(Permission.name == name).first()
        if not perm:
            perm = Permission(
                name=name,
                description=desc,
                created_at=datetime.utcnow()
            )
            db.add(perm)
            db.commit()
            db.refresh(perm)
            created_permissions.append(perm)
            print(f"   ➕ Permission erstellt: {name}")
        else:
            print(f"   ℹ Permission existiert bereits: {name}")

        # Admin bekommt jedes Recht
        role_perm = (
            db.query(RolePermission)
            .filter(RolePermission.role_id == admin_role.id,
                    RolePermission.permission_id == perm.id)
            .first()
        )
        if not role_perm:
            db.add(RolePermission(role_id=admin_role.id, permission_id=perm.id))
            db.commit()

    print("✔ Alle Permissions angelegt & Admin zugewiesen.")

    # -----------------------------------------------------
    # 3) ADMIN USER
    # -----------------------------------------------------
    admin_user = db.query(User).filter(User.username == "admin").first()
    if not admin_user:
        admin_user = User(
            username="admin",
            email="admin@example.com",
            password_hash=hash_password("Admin123!"),
            active=True,
            deleted=False,
            role_id=admin_role.id,
            must_change_password=False,
            created_at=datetime.utcnow()
        )
        db.add(admin_user)
        db.commit()
        print("✔ Admin-Benutzer erstellt (Admin123!)")
    else:
        print("ℹ Admin-Benutzer existiert bereits.")

    db.close()
    print("🎉 Seeding erfolgreich abgeschlossen!")


if __name__ == "__main__":
    run_seed()
