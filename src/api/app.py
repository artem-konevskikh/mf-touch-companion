"""
FastAPI Web Application for Touch Companion

This module sets up the FastAPI web application with:
- API endpoints for touch data and statistics
- Server-sent events for real-time updates
- Static file serving for web interface
- Error handling and logging
"""

import asyncio
import logging
import os
from typing import Dict, List, Any, Optional

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

# Import application modules
from modules.database import db
from modules.emotional_state import EmotionalStateEngine
from modules.sensor import TouchSensorManager
from modules.statistics import StatisticsEngine
from api.sse import EventManager, SSEResponse

# Include API routes
from api.routes.touch_data import router as touch_data_router
from api.routes.statistics import router as statistics_router
from api.routes.emotional_state import router as emotional_state_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("data/api.log"), logging.StreamHandler()],
)
logger = logging.getLogger("api")

# Create FastAPI application
app = FastAPI(
    title="Touch Companion API",
    description="API for the touch-sensitive companion device",
    version="1.0.0",
)

# Create module instances
emotional_state_engine = EmotionalStateEngine()
touch_sensor_manager = TouchSensorManager(emotional_state_engine)
statistics_engine = StatisticsEngine()

# Create event manager for SSE
event_manager = EventManager()

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files directory
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

# Set up templates
templates = Jinja2Templates(directory="frontend/templates")


@app.on_event("startup")
async def startup_event():
    """Initialize all modules on application startup."""
    logger.info("Starting Touch Companion API")

    # Initialize database
    await db.initialize()
    logger.info("Database initialized")

    # Initialize emotional state engine
    if await emotional_state_engine.initialize():
        logger.info("Emotional state engine initialized")
    else:
        logger.error("Failed to initialize emotional state engine")

    # Register state change callback for SSE
    emotional_state_engine.register_state_changed_callback(
        lambda state_info: event_manager.emit("state_change", state_info)
    )

    # Start sensor manager
    await touch_sensor_manager.initialize()
    await touch_sensor_manager.start()
    logger.info("Touch sensor manager started")

    # Register touch event callback for SSE
    touch_sensor_manager.register_callback(
        lambda event_data: event_manager.emit("touch_event", event_data)
    )

    # Start statistics engine
    await statistics_engine.start()
    logger.info("Statistics engine started")

    # Register statistics update callback for SSE
    statistics_engine.register_stats_changed_callback(
        lambda stats: event_manager.emit("statistics_update", stats)
    )

    logger.info("Touch Companion API startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up and stop all modules on application shutdown."""
    logger.info("Shutting down Touch Companion API")

    # Stop statistics engine
    await statistics_engine.stop()

    # Stop sensor manager
    await touch_sensor_manager.stop()

    # Run database optimization (async)
    try:
        await db.optimize_database()
    except Exception as e:
        logger.error(f"Error optimizing database: {str(e)}")

    logger.info("Touch Companion API shutdown complete")


app.include_router(touch_data_router, prefix="/api/touch", tags=["touch"])
app.include_router(statistics_router, prefix="/api/statistics", tags=["statistics"])
app.include_router(
    emotional_state_router, prefix="/api/emotional-state", tags=["emotional-state"]
)


# Server-sent events endpoint
@app.get("/api/events", response_class=SSEResponse)
async def events(request: Request):
    """
    Server-sent events endpoint for real-time updates.

    Provides events for:
    - touch_event: New touch event data
    - state_change: Emotional state changes
    - statistics_update: Updated statistics
    """

    async def event_generator():
        queue = asyncio.Queue()

        # Register this client
        client_id = event_manager.register_client(queue)

        try:
            # Send initial data
            stats = await statistics_engine.get_all_statistics()
            await queue.put({"event": "statistics_update", "data": stats})

            state_info = {
                "state": await emotional_state_engine.get_current_state(),
                "timestamp": stats["timestamp"],
            }
            await queue.put({"event": "state_change", "data": state_info})

            # Process events
            while True:
                # Wait for new events
                event = await queue.get()

                # Check if client is still connected
                if await request.is_disconnected():
                    break

                # Send event to client
                yield event

        except asyncio.CancelledError:
            # Client disconnected
            pass
        finally:
            # Clean up
            event_manager.unregister_client(client_id)

    return event_generator()


# Main page route
@app.get("/", response_class=HTMLResponse)
async def main_page(request: Request):
    """Serve the main page."""
    return templates.TemplateResponse("main.html", {"request": request})


# Statistics page route
@app.get("/statistics", response_class=HTMLResponse)
async def statistics_page(request: Request):
    """Serve the statistics page."""
    return templates.TemplateResponse("statistics.html", {"request": request})


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "sensor": touch_sensor_manager.get_sensor_status(),
        "emotional_state": emotional_state_engine.get_state_info(),
    }
