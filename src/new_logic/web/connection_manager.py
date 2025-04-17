from typing import List
import asyncio
from fastapi import WebSocket


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Accepts a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """Removes a WebSocket connection."""
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Sends a message to a specific WebSocket connection."""
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        """Sends a message to all active WebSocket connections."""
        # Use asyncio.gather for potentially faster broadcasting
        tasks = [conn.send_text(message) for conn in self.active_connections]
        await asyncio.gather(*tasks, return_exceptions=True)  # Handle potential errors


# Global instance (can be imported elsewhere)
manager = ConnectionManager()
