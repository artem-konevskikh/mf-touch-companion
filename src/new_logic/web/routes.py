from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pathlib import Path
import json

from src.new_logic.web.connection_manager import manager
# We will need access to the tracker and state manager instances later
# These will likely be passed in or accessed globally (depending on main_new.py structure)

router = APIRouter()

# Path to the HTML template
HTML_FILE = Path(__file__).parent / "templates" / "index.html"


@router.get("/")
async def get():
    """Serves the main HTML page."""
    try:
        with open(HTML_FILE, "r") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content, status_code=200)
    except FileNotFoundError:
        return HTMLResponse(
            content="<html><body><h1>Error: index.html not found</h1></body></html>",
            status_code=500,
        )


@router.websocket("/ws/stats")
async def websocket_endpoint(websocket: WebSocket):
    """Handles WebSocket connections for real-time stats."""
    await manager.connect(websocket)
    print("WebSocket client connected")
    try:
        # Keep the connection alive
        while True:
            # We don't expect messages from the client in this simple case
            # but FastAPI requires an await point
            await websocket.receive_text()  # Or receive_bytes, etc.
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print("WebSocket client disconnected")
    except Exception as e:
        print(f"WebSocket Error: {e}")
        manager.disconnect(websocket)


async def broadcast_stats(stats: dict):
    """Broadcasts stats to all connected WebSocket clients."""
    await manager.broadcast(json.dumps(stats))
