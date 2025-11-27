# app/routes/pulver.py

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from datetime import datetime
from app.auth import get_current_user, require_permission
from sqlalchemy.exc import IntegrityError
from app.utils import generate_barcode_base64
from app.database import get_db
from app.models import Pulver, PulverBewegung, User
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from ..ws_manager import manager
import asyncio

templates = Jinja2Templates(directory="app/templates")

# ❗ KEIN globales dependencies mehr – sonst ist Label immer geschützt
router = APIRouter(
    prefix="/api/pulver",
    tags=["Pulver"]
)

# ------------------------------------------------------------
# 🔹 1. Alle Pulver abrufen  (geschützt)
# ------------------------------------------------------------
@router.get("/", dependencies=[Depends(get_current_user)])
def get_all_pulver(db: Session = Depends(get_db)):
    pulver = db.query(Pulver).filter(Pulver.deleted == False).all()

    result = []
    for p in pulver:
        result.append({
            "id": p.id,
            "barcode": p.barcode,
            "artikelnummer": p.artikelnummer,
            "hersteller": p.hersteller,
            "farbe": p.farbe,
            "qualitaet": p.qualitaet,
            "oberflaeche": p.oberflaeche,
            "anwendung": p.anwendung,
            "start_menge_kg": p.start_menge_kg,
            "menge_kg": p.menge_kg,
            "lagerort": p.lagerort,
            "aktiv": p.aktiv,
            "created_by": p.created_by,
            "created_at": p.created_at,
        })
    return result

# ------------------------------------------------------------
# 🔹 2. Neues Pulver anlegen  (geschützt)
# ------------------------------------------------------------
@router.post("/", dependencies=[Depends(get_current_user)])
async def create_pulver(
    data: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    username = current_user.username

    artikelnummer = data.get("artikelnummer")
    hersteller = data.get("hersteller")
    farbe = data.get("farbe")
    start_menge_kg = data.get("start_menge_kg")

    if not artikelnummer or not hersteller:
        raise HTTPException(status_code=400, detail="Artikelnummer und Hersteller sind Pflichtfelder")

    existing = db.query(Pulver).filter(Pulver.artikelnummer == artikelnummer).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Artikelnummer '{artikelnummer}' existiert bereits")

    last_pulver = db.query(Pulver).order_by(Pulver.id.desc()).first()
    next_id = (last_pulver.id + 1) if last_pulver else 1
    barcode = f"OZS-{next_id:05d}"

    new_pulver = Pulver(
        barcode=barcode,
        artikelnummer=artikelnummer,
        hersteller=hersteller,
        farbe=farbe,
        qualitaet=data.get("qualitaet"),
        oberflaeche=data.get("oberflaeche"),
        anwendung=data.get("anwendung"),
        start_menge_kg=start_menge_kg,
        menge_kg=start_menge_kg,
        lagerort=data.get("lagerort"),
        aktiv=True,
        deleted=False,
        created_by=username,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    try:
        db.add(new_pulver)
        db.commit()
        db.refresh(new_pulver)

    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Fehler: Artikelnummer oder Barcode bereits vorhanden")
    
    asyncio.create_task(manager.broadcast({
        "event": "pulver_created",
        "id": new_pulver.id,
        "barcode": new_pulver.barcode,
        "artikelnummer": new_pulver.artikelnummer,
    }))

    return {
        "message": "Pulver erfolgreich angelegt",
        "pulver": {
            "id": new_pulver.id,
            "barcode": new_pulver.barcode,
            "artikelnummer": new_pulver.artikelnummer,
            "hersteller": new_pulver.hersteller,
            "menge_kg": new_pulver.menge_kg,
        },
    }

# ------------------------------------------------------------
# 🔹 3. Pulver bearbeiten  (geschützt)
# ------------------------------------------------------------
@router.put("/{pulver_id}", dependencies=[Depends(get_current_user)])
async def update_pulver(pulver_id: int, data: dict = Body(...), db: Session = Depends(get_db)):
    pulver = db.query(Pulver).filter(Pulver.id == pulver_id, Pulver.deleted == False).first()
    if not pulver:
        raise HTTPException(status_code=404, detail="Pulver nicht gefunden")

    # 🟡 1. Optimistic Locking: Prüfen, ob updated_at mitgeschickt wurde
    client_timestamp = data.get("updated_at")
    if not client_timestamp:
        raise HTTPException(status_code=400, detail="updated_at - Wert fehlt (Optimistic Locking)")

    # 🟡 2. Vergleich mit DB-Wert
    #    wir wandeln beide in ISO-Strings um, damit alles konsistent ist
    server_timestamp = pulver.updated_at.isoformat()

    if client_timestamp != server_timestamp:
        raise HTTPException(
            status_code=409,
            detail="Der Datensatz wurde inzwischen von einem anderen Benutzer geändert."
        )

    # 🟢 3. Wenn Version OK → Änderungen übernehmen
    for field in ["artikelnummer", "hersteller", "farbe", "qualitaet", "oberflaeche", "anwendung", "start_menge_kg", "lagerort", "aktiv"]:
        if field in data:
            setattr(pulver, field, data[field])

    pulver.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(pulver)

    asyncio.create_task(manager.broadcast({
        "event": "pulver_updated",
        "id": pulver.id
    }))

    return {
        "message": "Pulver erfolgreich aktualisiert",
        "id": pulver.id,
        "updated_at": pulver.updated_at  # Wichtig für das Frontend
    }

# ------------------------------------------------------------
# 🔹 4. Pulver Label erstellen  (öffentliche Route!)
# ------------------------------------------------------------
@router.get("/{pulver_id}/label", response_class=HTMLResponse)
def get_label(pulver_id: int, db: Session = Depends(get_db)):
    pulver = db.query(Pulver).filter_by(id=pulver_id).first()
    if not pulver:
        raise HTTPException(status_code=404, detail="Pulver nicht gefunden")

    barcode_image = generate_barcode_base64(pulver.barcode)

    return templates.TemplateResponse(
        "etikett.html",
        {
            "request": {},
            "pulver": pulver,
            "barcode_image": barcode_image,
        },
    )

# ------------------------------------------------------------
# 🔹 5. Pulver Tracken  (geschützt)
# ------------------------------------------------------------
@router.post("/track", dependencies=[Depends(require_permission("pulver.track"))])
async def track_pulver(
    data: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    barcode = data.get("barcode")
    menge_neu = data.get("menge_neu")
    beschreibung = data.get("beschreibung", "Normaler Verbrauch")

    if not barcode or menge_neu is None:
        raise HTTPException(status_code=400, detail="Barcode und neue Menge erforderlich")

    pulver = db.query(Pulver).filter(Pulver.barcode == barcode, Pulver.deleted == False).first()
    if not pulver:
        raise HTTPException(status_code=404, detail="Pulver nicht gefunden")

    menge_alt = pulver.menge_kg

    bewegung = PulverBewegung(
        pulver_id=pulver.id,
        barcode=barcode,
        datum=datetime.utcnow(),
        menge_alt=menge_alt,
        menge_neu=menge_neu,
        beschreibung=beschreibung,
        user_id=current_user.id,
    )
    db.add(bewegung)

    pulver.menge_kg = menge_neu
    db.commit()

    asyncio.create_task(manager.broadcast({
        "event": "pulver_tracked",
        "id": pulver.id,
        "barcode": barcode,
        "menge_neu": menge_neu
    }))

    return {
        "message": "Bewegung gespeichert",
        "menge_alt": menge_alt,
        "menge_neu": menge_neu,
        "beschreibung": beschreibung
    }

# ------------------------------------------------------------
# 🔹 6. Pulver über Barcode abrufen  (geschützt)
# ------------------------------------------------------------
@router.get("/{barcode}", dependencies=[Depends(get_current_user)])
def get_pulver_by_barcode(barcode: str, db: Session = Depends(get_db)):
    pulver = db.query(Pulver).filter(Pulver.barcode == barcode, Pulver.deleted == False).first()

    if not pulver:
        raise HTTPException(status_code=404, detail="Pulver nicht gefunden")

    return {
        "id": pulver.id,
        "barcode": pulver.barcode,
        "artikelnummer": pulver.artikelnummer,
        "hersteller": pulver.hersteller,
        "farbe": pulver.farbe,
        "qualität": pulver.qualitaet,
        "oberfläche": pulver.oberflaeche,
        "anwendung": pulver.anwendung,
        "menge_kg": pulver.menge_kg,
        "lagerort": pulver.lagerort,
        "aktiv": pulver.aktiv,
    }

# ------------------------------------------------------------
# 🔹 7. Pulver löschen (Soft Delete)
# ------------------------------------------------------------
@router.delete("/{pulver_id}", dependencies=[Depends(require_permission("powder.delete"))])
async def delete_pulver(pulver_id: int, db: Session = Depends(get_db)):
    pulver = db.query(Pulver).filter(Pulver.id == pulver_id, Pulver.deleted == False).first()

    if not pulver:
        raise HTTPException(status_code=404, detail="Pulver nicht gefunden")

    pulver.deleted = True
    pulver.updated_at = datetime.utcnow()
    db.commit()

    asyncio.create_task(manager.broadcast({
        "event": "pulver_deleted",
        "id": pulver.id
    }))

    return {"message": "Pulver erfolgreich gelöscht (Soft Delete)"}

# ------------------------------------------------------------
# 🔹 8. Pulver Daten holen 
# ------------------------------------------------------------
@router.get("/id/{pulver_id}", dependencies=[Depends(get_current_user)])
def get_pulver_by_id(pulver_id: int, db: Session = Depends(get_db)):
    pulver = db.query(Pulver).filter(Pulver.id == pulver_id, Pulver.deleted == False).first()

    if not pulver:
        raise HTTPException(status_code=404, detail="Pulver nicht gefunden")

    return {
        "id": pulver.id,
        "barcode": pulver.barcode,
        "artikelnummer": pulver.artikelnummer,
        "hersteller": pulver.hersteller,
        "farbe": pulver.farbe,
        "qualitaet": pulver.qualitaet,
        "oberflaeche": pulver.oberflaeche,
        "anwendung": pulver.anwendung,
        "start_menge_kg": pulver.start_menge_kg,
        "menge_kg": pulver.menge_kg,
        "lagerort": pulver.lagerort,
        "aktiv": pulver.aktiv,
        "updated_at": pulver.updated_at
    }
