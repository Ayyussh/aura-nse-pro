"""AURA-NSE Pro FastAPI Main Application.

Configures CORS, authentication, REST routers, background APScheduler,
and real-time WebSockets for AURA Humanoid state events.
"""

from __future__ import annotations
import asyncio
import datetime
import logging
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.auth import router as auth_router
from backend.api.endpoints import router as api_router
from backend.core.config import settings
from backend.core.ops_monitor import configure_rotating_logger, check_disk_space
from backend.db.init_db import init_database
from backend.jobs.scheduler import start_scheduler, get_ist_now

# Configure Rotating File Logging (10MB, 5 backups)
configure_rotating_logger()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("aura.main")


class WebSocketConnectionManager:
    """Manages active browser WebSocket connections for live UI push updates."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)


ws_manager = WebSocketConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup & shutdown events."""
    logger.info("Initializing AURA-NSE Pro database and tables...")
    init_database()
    logger.info("Starting background APScheduler in Asia/Kolkata timezone...")
    start_scheduler()
    yield
    logger.info("Shutting down AURA-NSE Pro...")


app = FastAPI(
    title="AURA-NSE Pro — Investor-Grade Humanoid AI Indian Stock System",
    description="Institutional Decision-Support and 30-Day Stress-Test Platform for NSE/BSE Equities.",
    version="2.0.0",
    lifespan=lifespan,
)

# Locked CORS Configuration (Localhost binding only - Section 19.2)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import os
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Register API Routers
app.include_router(auth_router)
app.include_router(api_router)

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/")
    def serve_frontend_root():
        return FileResponse(FRONTEND_DIST / "index.html")

    @app.get("/status")
    def api_status_endpoint():
        return {
            "app": "AURA-NSE Pro",
            "version": "2.0.0",
            "status": "ONLINE",
            "ist_time": get_ist_now().isoformat(),
            "compliance": "Educational decision support, not investment advice.",
            "docs_url": "/docs",
        }
else:
    @app.get("/")
    def root():
        return {
            "app": "AURA-NSE Pro",
            "version": "2.0.0",
            "status": "ONLINE",
            "ist_time": get_ist_now().isoformat(),
            "compliance": "Educational decision support, not investment advice.",
            "docs_url": "/docs",
        }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Live WebSocket stream for AURA avatar state changes and system notifications."""
    await ws_manager.connect(websocket)
    try:
        # Initial greeting event
        await websocket.send_json({
            "type": "AURA_STATE",
            "state": "Idle",
            "message": "AURA AI Analyst connected and listening.",
            "timestamp": datetime.datetime.utcnow().isoformat(),
        })
        while True:
            data = await websocket.receive_text()
            # Heartbeat pong
            await websocket.send_json({
                "type": "HEARTBEAT_ACK",
                "received": data,
                "timestamp": datetime.datetime.utcnow().isoformat(),
            })
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.warning(f"WebSocket connection error: {e}")
        ws_manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    # Institutional security binding: strictly localhost loopback 127.0.0.1
    uvicorn.run("backend.main:app", host="127.0.0.1", port=settings.PORT, reload=True)
