import json
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from src.web.connection_manager import manager as stats_manager
from src.web.connection_manager import ConnectionManager

# Create a separate manager for API response websockets
api_response_manager = ConnectionManager()

router = APIRouter()

# Paths to the HTML templates
INDEX_HTML_FILE = Path(__file__).parent / "templates" / "index.html"
RESPONSE_HTML_FILE = Path(__file__).parent / "templates" / "response.html"


@router.get("/")
async def get_index():
    """Serves the main HTML page."""
    try:
        with open(INDEX_HTML_FILE, "r") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content, status_code=200)
    except FileNotFoundError:
        return HTMLResponse(
            content="<html><body><h1>Error: index.html not found</h1></body></html>",
            status_code=500,
        )


@router.get("/response")
async def get_response_page():
    """Serves the API response HTML page."""
    try:
        with open(RESPONSE_HTML_FILE, "r") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content, status_code=200)
    except FileNotFoundError:
        return HTMLResponse(
            content="<html><body><h1>Error: response.html not found</h1></body></html>",
            status_code=500,
        )


@router.websocket("/ws/stats")
async def websocket_stats_endpoint(websocket: WebSocket):
    """Handles WebSocket connections for real-time stats."""
    await stats_manager.connect(websocket)
    print("WebSocket stats client connected")
    try:
        # Keep the connection alive
        while True:
            # We don't expect messages from the client in this simple case
            # but FastAPI requires an await point
            await websocket.receive_text()  # Or receive_bytes, etc.
    except WebSocketDisconnect:
        stats_manager.disconnect(websocket)
        print("WebSocket stats client disconnected")
    except Exception as e:
        print(f"WebSocket Error: {e}")
        stats_manager.disconnect(websocket)


@router.websocket("/ws/api_response")
async def websocket_api_response_endpoint(websocket: WebSocket):
    """Handles WebSocket connections for API responses."""
    await api_response_manager.connect(websocket)
    print("WebSocket API response client connected")
    try:
        # Keep the connection alive
        while True:
            # We don't expect messages from the client in this simple case
            # but FastAPI requires an await point
            await websocket.receive_text()
    except WebSocketDisconnect:
        api_response_manager.disconnect(websocket)
        print("WebSocket API response client disconnected")
    except Exception as e:
        print(f"WebSocket Error: {e}")
        api_response_manager.disconnect(websocket)


async def broadcast_stats(stats: dict):
    """Broadcasts stats to all connected WebSocket clients."""
    await stats_manager.broadcast(json.dumps(stats))


async def broadcast_api_response(response_data: dict):
    """Broadcasts API response to all connected WebSocket clients."""
    await api_response_manager.broadcast(json.dumps(response_data))
