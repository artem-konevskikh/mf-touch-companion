"""
API routes for the web application.
"""

import asyncio
import logging
import time
from typing import List

from fastapi import APIRouter, Request, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from src.database import Database
from src.emotional_state_engine import EmotionalStateEngine, EmotionalStateType
from src.webapp.models import ApiResponse, TouchStatistics

import json

router = APIRouter(prefix="/api")

# Logger
logger = logging.getLogger(__name__)

# Global references to services - will be set during app initialization
database: Database | None = None
emotional_state_engine: EmotionalStateEngine | None = None
update_interval = 5.0  # Default update interval in seconds


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error sending message to WebSocket: {e}")


# Create a connection manager instance
manager = ConnectionManager()


def get_database():
    """Get the database dependency."""
    if database is None:
        raise RuntimeError("Database not initialized")
    return database


def get_emotional_state_engine():
    """Get the emotional state engine dependency."""
    if emotional_state_engine is None:
        raise RuntimeError("Emotional state engine not initialized")
    return emotional_state_engine


def init_services(db: Database, engine: EmotionalStateEngine, interval: float = 5.0):
    """Initialize the service dependencies."""
    global database, emotional_state_engine, update_interval
    database = db
    emotional_state_engine = engine
    update_interval = interval


def get_touch_statistics(
    db: Database = Depends(get_database),
    engine: EmotionalStateEngine = Depends(get_emotional_state_engine),
) -> TouchStatistics:
    """Get current touch statistics.

    Args:
        db: The database instance
        engine: The emotional state engine instance

    Returns:
        TouchStatistics object with current statistics
    """
    current_state = engine.get_current_state()

    return TouchStatistics(
        total_count=db.get_total_touch_count(),
        hour_count=db.get_touch_count_last_hour(),
        today_count=db.get_touch_count_today(),
        avg_duration=db.get_average_touch_duration(),
        emotional_state=current_state.value,
        emotional_state_emoji=engine.get_state_emoji(),
        emotional_state_time=db.get_time_in_emotional_states_today(),
        last_update=time.time(),
    )


@router.get("/statistics", response_model=ApiResponse)
async def get_statistics(statistics: TouchStatistics = Depends(get_touch_statistics)):
    """Get touch statistics."""
    try:
        return ApiResponse(success=True, data=statistics)
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        return ApiResponse(success=False, error=str(e))


@router.websocket("/ws/statistics")
async def websocket_statistics(websocket: WebSocket):
    """WebSocket endpoint for statistics updates."""
    await manager.connect(websocket)
    
    try:
        # Send initial statistics
        stats = get_touch_statistics(
            get_database(), get_emotional_state_engine()
        )
        await websocket.send_text(ApiResponse(success=True, data=stats).json())
        
        # Keep the connection alive and send periodic updates
        while True:
            try:
                # Wait for the update interval or for a message from the client
                # Use wait_for with a timeout to handle both cases
                receive_task = asyncio.create_task(websocket.receive_text())
                update_task = asyncio.create_task(asyncio.sleep(update_interval))
                
                done, pending = await asyncio.wait(
                    [receive_task, update_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # Cancel the pending task
                for task in pending:
                    task.cancel()
                
                # Handle client message (ping)
                if receive_task in done:
                    try:
                        message = receive_task.result()
                        data = json.loads(message)
                        
                        # Handle ping message
                        if data.get('type') == 'ping':
                            await websocket.send_text(json.dumps({'type': 'pong'}))
                    except Exception as e:
                        logger.error(f"Error processing client message: {e}")
                
                # Send periodic update
                if update_task in done:
                    # Get fresh statistics
                    stats = get_touch_statistics(
                        get_database(), get_emotional_state_engine()
                    )
                    
                    # Send the update
                    await websocket.send_text(ApiResponse(success=True, data=stats).json())
                
            except Exception as e:
                logger.error(f"Error in WebSocket communication: {e}")
                await websocket.send_text(ApiResponse(success=False, error=str(e)).json())
                await asyncio.sleep(1)  # Wait a bit before trying again
                
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Remove this connection when done
        manager.disconnect(websocket)


# Keep the SSE endpoint for backward compatibility
@router.get("/events/statistics")
async def sse_statistics(request: Request):
    """Server-sent events for statistics updates (legacy endpoint)."""

    # Create a queue for touch events
    queue: asyncio.Queue = asyncio.Queue()
    
    # Register this queue in a global registry
    # This is a simple way to broadcast events to all connected clients
    if not hasattr(sse_statistics, "active_connections"):
        sse_statistics.active_connections = set()
    
    # Add this connection to the set
    sse_statistics.active_connections.add(queue)
    
    async def event_generator():
        """Generate SSE events."""
        try:
            # Send initial statistics
            stats = get_touch_statistics(
                get_database(), get_emotional_state_engine()
            )
            yield f"data: {stats.json()}\n\n"
            
            while True:
                # If client disconnects, stop sending events
                if await request.is_disconnected():
                    break
                    
                try:
                    # Either wait for a new touch event or timeout after update_interval
                    try:
                        # Wait for a touch event (or timeout)
                        await asyncio.wait_for(queue.get(), timeout=update_interval)
                        
                        # Get fresh statistics after a touch event
                        stats = get_touch_statistics(
                            get_database(), get_emotional_state_engine()
                        )
                        
                        # Format as SSE
                        yield f"data: {stats.json()}\n\n"
                        
                    except asyncio.TimeoutError:
                        # Timeout occurred, send periodic update
                        stats = get_touch_statistics(
                            get_database(), get_emotional_state_engine()
                        )
                        yield f"data: {stats.json()}\n\n"
                        
                except Exception as e:
                    logger.error(f"Error generating SSE: {e}")
                    yield f"data: {ApiResponse(success=False, error=str(e)).json()}\n\n"
                    # Wait a bit before trying again
                    await asyncio.sleep(1)
                    
        finally:
            # Remove this connection when done
            if hasattr(sse_statistics, "active_connections"):
                sse_statistics.active_connections.remove(queue)

    return EventSourceResponse(event_generator())


# Function to notify all clients about new touch events
async def notify_touch_event():
    """Notify all connected clients about a new touch event."""
    # Notify SSE clients
    if hasattr(sse_statistics, "active_connections"):
        for queue in sse_statistics.active_connections:
            # Put a notification in each client's queue
            try:
                queue.put_nowait(None)  # None is just a signal, the actual data will be fetched fresh
            except Exception as e:
                logger.error(f"Error notifying SSE client: {e}")
    
    # Notify WebSocket clients
    try:
        # Get fresh statistics
        stats = get_touch_statistics(
            get_database(), get_emotional_state_engine()
        )
        # Broadcast to all WebSocket clients
        await manager.broadcast(ApiResponse(success=True, data=stats).json())
    except Exception as e:
        logger.error(f"Error broadcasting to WebSocket clients: {e}")

@router.post("/state/{state}", response_model=ApiResponse)
async def set_emotional_state(
    state: str, engine: EmotionalStateEngine = Depends(get_emotional_state_engine)
):
    """Manually set the emotional state."""
    try:
        state_enum = EmotionalStateType(state.lower())
        engine.force_state(state_enum)
        return ApiResponse(success=True)
    except ValueError:
        return ApiResponse(
            success=False,
            error=f"Invalid state: {state}. Valid states: {[s.value for s in EmotionalStateType]}",
        )
    except Exception as e:
        logger.error(f"Error setting state: {e}")
        return ApiResponse(success=False, error=str(e))


# Server-sent events response
class EventSourceResponse(JSONResponse):
    """Server-sent events response."""

    media_type = "text/event-stream"

    def __init__(
        self, content, status_code=200, headers=None, media_type=None, background=None
    ):
        self.content_generator = content
        super().__init__(
            content={},  # Empty content as we'll stream it
            status_code=status_code,
            headers=headers or {},
            media_type=media_type,
            background=background,
        )

    def render(self, content):
        return b""  # Return empty bytes as content is streamed in __call__

    async def __call__(self, scope, receive, send):
        # Set appropriate headers for SSE
        headers = [
            (b"content-type", b"text/event-stream"),
            (b"cache-control", b"no-cache"),
            (b"connection", b"keep-alive"),
        ]

        # Send initial response headers
        await send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": headers,
            }
        )

        # Stream the content from the generator
        async for data in self.content_generator:
            payload = data.encode("utf-8")
            await send(
                {"type": "http.response.body", "body": payload, "more_body": True}
            )

        # Send final empty body chunk to close the response
        await send({"type": "http.response.body", "body": b"", "more_body": False})
