"""
Main FastAPI application for the touch sensor companion device.

This module provides the FastAPI application setup and initialization.
"""

import logging
from pathlib import Path
from typing import Union

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.database import Database
from src.emotional_state_engine import EmotionalStateEngine
from src.webapp.routes.api import router as api_router
from src.webapp.routes.views import router as views_router
from src.webapp.routes.api import init_services
from src.webapp.routes.views import init_templates

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Create FastAPI application
app = FastAPI(
    title="Touch Sensor Companion",
    description="API and web interface for the touch sensor companion device",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class WebApp:
    """Web application for the touch sensor companion device."""

    def __init__(
        self,
        database: Database,
        emotional_state_engine: EmotionalStateEngine,
        host: str = "0.0.0.0",
        port: int = 8000,
        static_dir: Union[str, Path] = Path("src/webapp/static"),
        templates_dir: Union[str, Path] = Path("src/webapp/templates"),
        update_interval: float = 1.0,
    ) -> None:
        """Initialize the web application.

        Args:
            database: The database instance
            emotional_state_engine: The emotional state engine
            host: Host to bind to
            port: Port to bind to
            static_dir: Directory for static files
            templates_dir: Directory for templates
            update_interval: Interval for SSE updates in seconds
        """
        self.database = database
        self.emotional_state_engine = emotional_state_engine
        self.host = host
        self.port = port
        self.static_dir = Path(static_dir)
        self.templates_dir = Path(templates_dir)
        self.update_interval = update_interval

        # Create directories if they don't exist
        self.static_dir.mkdir(parents=True, exist_ok=True)
        self.templates_dir.mkdir(parents=True, exist_ok=True)

        # Initialize the application
        self._setup_app()

        logger.info(f"Web application initialized on {host}:{port}")

    def _setup_app(self) -> None:
        """Set up the FastAPI application."""
        # Initialize services and templates
        init_services(self.database, self.emotional_state_engine, self.update_interval)
        init_templates(self.templates_dir)

        # Mount static files
        app.mount("/static", StaticFiles(directory=str(self.static_dir)), name="static")

        # Include routers
        app.include_router(views_router)
        app.include_router(api_router)

    def run(self) -> None:
        """Run the web application."""
        uvicorn.run(app, host=self.host, port=self.port)


# Export the app for testing
__all__ = ["app", "WebApp"]
