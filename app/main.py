from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.database import Base, engine
from app.routes import auth, users, roles, pulver
from fastapi import WebSocket
from .ws_manager import manager
from fastapi import WebSocketDisconnect

Base.metadata.create_all(bind=engine)

app = FastAPI()

# statische Dateien einbinden
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")

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

@app.websocket("/ws/app")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)