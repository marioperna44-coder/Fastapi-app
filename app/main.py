from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.database import Base, engine
from app.routes import auth, users, roles, pulver
from fastapi import WebSocket
from .ws_manager import manager
from fastapi import WebSocketDisconnect
from app.seed_permissions import run_seed

# *** WICHTIGE KORREKTUR: PATHLIB FÜR ROBUSTE PFADE ***
from pathlib import Path

# Definiere das Basisverzeichnis (Basis ist der Ordner, in dem diese Datei liegt: 'app/')
BASE_DIR = Path(__file__).resolve().parent

# Datenbank-Tabellen erstellen
Base.metadata.create_all(bind=engine)

run_seed()

app = FastAPI()

# Statische Dateien einbinden
# Verwenden des absoluten Pfades: BASE_DIR / "static"
app.mount(
    "/static", 
    StaticFiles(directory=BASE_DIR / "static"), 
    name="static"
)

# Templates
# Verwenden des absoluten Pfades: BASE_DIR / "templates"
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# --- STANDARD-ROUTEN (optional) ---
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# Router einbinden
app.include_router(auth.router, prefix="/api", tags=["Auth"])
app.include_router(roles.router)
app.include_router(users.router)
app.include_router(pulver.router)

# --- WEB SOCKETS ---
@app.websocket("/ws/app")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# ******************************************************************
# *** WICHTIGSTE HINZUFÜGUNG: CATCH-ALL ROUTER FÜR SPA FALLBACK ***
# ******************************************************************
# DIESE ROUTE MUSS DIE LETZTE ROUTE IN DER DATEI SEIN!
@app.get("/{full_path:path}", response_class=HTMLResponse)
async def serve_spa_app(request: Request):
    # Alle nicht übereinstimmenden Pfade (z.B. /dashboard) leiten wir auf die index.html um.
    # Das clientseitige JavaScript-Routing übernimmt dann die Anzeige des richtigen Inhalts.
    return templates.TemplateResponse("index.html", {"request": request})