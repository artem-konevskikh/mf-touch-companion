"""
API routes for the web application.
"""

import asyncio
import logging
import time
from typing import Callable

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse

from src.database import Database
from src.emotional_state_engine import EmotionalStateEngine, EmotionalStateType
from src.webapp.models import ApiResponse, TouchStatistics

router = APIRouter(prefix="/api")

# Logger
logger = logging.getLogger(__name__)

# Global references to services - will be set during app initialization
database = None
emotional_state_engine = None
update_interval = 5.0  # Default update interval in seconds


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


@router.get("/events/statistics")
async def sse_statistics(
    request: Request,
    get_stats: Callable[[], TouchStatistics] = Depends(get_touch_statistics),
):
    """Server-sent events for statistics updates."""

    async def event_generator():
        """Generate SSE events."""
        while True:
            # If client disconnects, stop sending events
            if await request.is_disconnected():
                break

            try:
                # Get current statistics
                stats = get_stats()

                # Format as SSE
                yield f"data: {stats.json()}\n\n"

            except Exception as e:
                logger.error(f"Error generating SSE: {e}")
                yield f"data: {ApiResponse(success=False, error=str(e)).json()}\n\n"

            # Wait before sending next update
            await asyncio.sleep(update_interval)

    return EventSourceResponse(event_generator())


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

    def render(self, content):
        return content.encode("utf-8")
