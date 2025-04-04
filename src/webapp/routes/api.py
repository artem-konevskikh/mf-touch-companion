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
update_interval = 1.0  # Default update interval in seconds


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        # Dictionary to store last sent statistics for each connection
        self.last_stats: Dict[WebSocket, TouchStatistics] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.last_stats[websocket] = None

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        if websocket in self.last_stats:
            del self.last_stats[websocket]

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error sending message to WebSocket: {e}")
                
    async def broadcast_stats(self, stats: TouchStatistics):
        """Broadcast statistics to all connections only if they changed for each connection.
        
        Args:
            stats: The current statistics
        """
        for connection in self.active_connections:
            await self.send_stats_if_changed(connection, stats)
                
    async def send_stats_if_changed(self, connection: WebSocket, stats: TouchStatistics) -> bool:
        """Send statistics to a connection only if they have changed.
        
        Args:
            connection: The WebSocket connection
            stats: The current statistics
            
        Returns:
            bool: True if statistics were sent, False otherwise
        """
        last_stats = self.last_stats.get(connection)
        
        # If no previous stats or stats have changed, send update
        if last_stats is None or self._stats_changed(last_stats, stats):
            try:
                await connection.send_text(ApiResponse(success=True, data=stats).json())
                self.last_stats[connection] = stats
                return True
            except Exception as e:
                logger.error(f"Error sending update: {e}")
        
        return False
    
    def _stats_changed(self, old_stats: TouchStatistics, new_stats: TouchStatistics) -> bool:
        """Check if statistics have changed significantly.
        
        Args:
            old_stats: Previous statistics
            new_stats: Current statistics
            
        Returns:
            bool: True if statistics have changed, False otherwise
        """
        # Compare all relevant fields except last_update
        return (
            old_stats.total_count != new_stats.total_count or
            old_stats.hour_count != new_stats.hour_count or
            old_stats.today_count != new_stats.today_count or
            abs(old_stats.avg_duration - new_stats.avg_duration) > 0.001 or
            old_stats.emotional_state != new_stats.emotional_state or
            old_stats.emotional_state_emoji != new_stats.emotional_state_emoji or
            old_stats.emotional_state_time != new_stats.emotional_state_time
        )


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


# Event queue for WebSocket notifications
# This will be used to notify WebSocket clients about touch events
websocket_event_queue: asyncio.Queue[None] = asyncio.Queue()

@router.websocket("/ws/statistics")
async def websocket_statistics(websocket: WebSocket):
    """WebSocket endpoint for statistics updates."""
    await manager.connect(websocket)
    
    # Flag to track connection state
    is_connected = True
    
    # Tasks to clean up
    tasks = []
    
    try:
        # Send initial statistics
        stats = get_touch_statistics(
            get_database(), get_emotional_state_engine()
        )
        # Initial statistics are always sent
        await websocket.send_text(ApiResponse(success=True, data=stats).json())
        manager.last_stats[websocket] = stats
        
        # Keep the connection alive and send periodic updates
        last_update_time = time.time()
        min_update_interval = 0.1  # Minimum time between updates (100ms)
        
        while is_connected:
            try:
                # Create tasks for each possible event
                receive_task = asyncio.create_task(websocket.receive_text())
                update_task = asyncio.create_task(asyncio.sleep(update_interval))
                event_task = asyncio.create_task(websocket_event_queue.get())
                
                # Keep track of tasks for cleanup
                tasks = [receive_task, update_task, event_task]
                
                # Wait for any task to complete
                done, pending = await asyncio.wait(
                    tasks,
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # Cancel pending tasks properly
                for task in pending:
                    task.cancel()
                    try:
                        # Wait for the task to be cancelled
                        await task
                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        logger.debug(f"Error cancelling task: {e}")
                
                # Clear tasks list
                tasks = []
                
                # Check if we're still connected
                if not is_connected:
                    break
                
                current_time = time.time()
                time_since_last_update = current_time - last_update_time
                should_update = False
                
                # Handle client message (ping)
                if receive_task in done:
                    try:
                        message = receive_task.result()
                        data = json.loads(message)
                        
                        # Handle ping message
                        if data.get('type') == 'ping':
                            await websocket.send_text(json.dumps({'type': 'pong'}))
                    except WebSocketDisconnect:
                        # Client disconnected
                        logger.info("WebSocket client disconnected during receive")
                        is_connected = False
                        break
                    except Exception as e:
                        logger.error(f"Error processing client message: {e}")
                
                # Handle touch event notification
                if event_task in done and is_connected:
                    # Only update if enough time has passed since the last update
                    if time_since_last_update >= min_update_interval:
                        should_update = True
                    else:
                        # If we're updating too frequently, put the event back in the queue
                        # for the next iteration
                        await websocket_event_queue.put(None)
                
                # Handle periodic update
                if update_task in done:
                    should_update = True
                
                # Send update if needed and still connected
                if should_update and is_connected:
                    try:
                        # Get fresh statistics
                        stats = get_touch_statistics(
                            get_database(), get_emotional_state_engine()
                        )
                        
                        # Only send update if statistics have changed
                        if await manager.send_stats_if_changed(websocket, stats):
                            last_update_time = current_time
                    except WebSocketDisconnect:
                        logger.info("WebSocket client disconnected during send")
                        is_connected = False
                        break
                    except Exception as e:
                        logger.error(f"Error sending update: {e}")
                
            except WebSocketDisconnect:
                logger.info("WebSocket client disconnected in main loop")
                is_connected = False
                break
            except asyncio.CancelledError:
                logger.info("WebSocket tasks cancelled")
                is_connected = False
                break
            except Exception as e:
                logger.error(f"Error in WebSocket communication: {e}")
                try:
                    if is_connected:
                        await websocket.send_text(ApiResponse(success=False, error=str(e)).json())
                        await asyncio.sleep(1)  # Wait a bit before trying again
                except Exception:
                    # If we can't send the error, the connection is probably closed
                    is_connected = False
                    break
                
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Cancel any remaining tasks
        for task in tasks:
            if not task.done():
                task.cancel()
        
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
        # Keep track of last sent statistics for this connection
        last_stats = None
        
        try:
            # Send initial statistics
            stats = get_touch_statistics(
                get_database(), get_emotional_state_engine()
            )
            yield f"data: {stats.json()}\n\n"
            last_stats = stats
            
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
                        
                        # Only send update if statistics have changed
                        if last_stats is None or manager._stats_changed(last_stats, stats):
                            # Format as SSE
                            yield f"data: {stats.json()}\n\n"
                            last_stats = stats
                        
                    except asyncio.TimeoutError:
                        # Timeout occurred, check if we need to send periodic update
                        stats = get_touch_statistics(
                            get_database(), get_emotional_state_engine()
                        )
                        
                        # Only send update if statistics have changed
                        if last_stats is None or manager._stats_changed(last_stats, stats):
                            yield f"data: {stats.json()}\n\n"
                            last_stats = stats
                        
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
async def notify_touch_event_async():
    """Notify all connected clients about a new touch event (async version)."""
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
        # Put an event in the WebSocket event queue for immediate notification
        await websocket_event_queue.put(None)
        
        # Also broadcast to all WebSocket clients directly
        # This ensures backward compatibility and handles cases where the WebSocket
        # connection might not be using the event queue yet
        stats = get_touch_statistics(
            get_database(), get_emotional_state_engine()
        )
        await manager.broadcast_stats(stats)
    except Exception as e:
        logger.error(f"Error broadcasting to WebSocket clients: {e}")


# Wrapper function that can be called from synchronous code
def notify_touch_event():
    """Notify all connected clients about a new touch event.
    
    This function can be called from synchronous code and will schedule
    the async notification in the event loop.
    """
    # Import asyncio here to avoid circular imports
    import asyncio
    
    # Get the current event loop or create a new one
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # If there's no event loop in the current thread, create a new one
        # This should not happen in normal operation but is here as a safeguard
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    # Schedule the async notification
    asyncio.run_coroutine_threadsafe(notify_touch_event_async(), loop)

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
