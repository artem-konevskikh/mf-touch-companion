#!/usr/bin/env python3
"""
Touch Companion Application Module.

Contains the main application class that drives the Touch Companion system.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, Optional, Union

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.new_logic.config import AppConfig
from src.hardware.led_strip import LedStrip
from src.new_logic.touch_tracker import TouchTracker
from src.new_logic.state_manager import StateManager
from src.new_logic.web import routes as web_routes
from src.new_logic.web.routes import broadcast_stats

# Configure logger
logger = logging.getLogger("touch_companion")


class TouchCompanionApp:
    """Main application class for Touch Companion system."""

    def __init__(self, config: AppConfig):
        """Initialize the application with the given configuration.

        Args:
            config: Application configuration parameters
        """
        self.config = config
        self.leds: Optional[LedStrip] = None
        self.tracker: Optional[TouchTracker] = None
        self.manager: Optional[StateManager] = None
        self.background_task_running = False

        # Setup logging configuration
        self._setup_logging()

        # Create FastAPI app
        self.app = FastAPI(lifespan=self._lifespan)
        self._setup_routes()

    def _setup_logging(self) -> None:
        """Configure application logging."""
        log_format = "%(asctime)s - %(levelname)s - %(message)s"

        # Reset existing handlers to avoid duplicate logs
        logger.handlers = []

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.WARNING)  # Set default level for all other loggers

        # Configure our application logger
        logger.setLevel(getattr(logging, self.config.log_level.upper()))

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(log_format))
        logger.addHandler(console_handler)

        # File handler (optional)
        if self.config.log_file:
            file_handler = logging.FileHandler(self.config.log_file)
            file_handler.setFormatter(logging.Formatter(log_format))
            logger.addHandler(file_handler)

    def _setup_routes(self) -> None:
        """Set up the web routes and static file serving."""
        # Mount static files (for CSS/JS)
        static_dir = Path(__file__).parent / "web" / "static"
        if static_dir.is_dir():
            self.app.mount(
                "/static", StaticFiles(directory=str(static_dir)), name="static"
            )
        else:
            logger.warning(f"Static directory not found at {static_dir}")

        # Include web routes
        self.app.include_router(web_routes.router)

    @asynccontextmanager
    async def _lifespan(self, app: FastAPI):
        """Handle application startup and shutdown.

        Args:
            app: The FastAPI application instance
        """
        # Startup logic
        logger.info("Starting Touch Companion application")
        self.background_task_running = True
        try:
            # Initialize LED strip
            led_device_path = Path(self.config.led_device)
            if not led_device_path.exists():
                logger.error(
                    f"LED device {self.config.led_device} not found. Check configuration."
                )
            else:
                self.leds = LedStrip(
                    device=self.config.led_device,
                    num_leds=self.config.num_leds,
                    frequency=self.config.led_frequency,
                )
                logger.info(f"LED strip initialized with {self.config.num_leds} LEDs")

            # Initialize Touch Tracker
            self.tracker = TouchTracker(
                i2c_address=self.config.i2c_address,
                i2c_bus=self.config.i2c_bus,
                history_duration_sec=self.config.history_duration_sec,
            )
            logger.info("Touch tracker initialized")

            # Initialize State Manager if LEDs are available
            if self.leds:
                self.manager = StateManager(
                    self.leds,
                    touch_threshold=self.config.touch_threshold,
                    sad_color=self.config.sad_color,
                    glad_color=self.config.glad_color,
                    transition_steps=self.config.transition_steps,
                )
                logger.info(
                    f"State manager initialized with threshold: {self.config.touch_threshold}"
                )
            else:
                logger.warning(
                    "State manager initialization skipped (LEDs not available)"
                )

            # Start the background task
            asyncio.create_task(self._sensor_monitor_task())

        except ImportError as e:
            logger.error(f"Import error during startup: {e}")
            logger.error(
                "Ensure required libraries are installed (smbus2, pi5neo, fastapi, uvicorn)"
            )
        except Exception as e:
            logger.error(f"Unexpected error during startup: {e}", exc_info=True)

        yield  # Application runs here

        # Shutdown logic
        logger.info("Application shutting down")
        self.background_task_running = False
        # Give the task a moment to finish gracefully
        await asyncio.sleep(self.config.update_interval_sec * 2)
        if self.leds:
            self.leds.clear()  # Turn off LEDs on exit
            logger.info("LED strip cleared")

    async def _sensor_monitor_task(self) -> None:
        """Run the core sensor reading and state update logic in the background."""
        logger.info("Sensor monitoring task started")
        while self.background_task_running:
            try:
                if self.tracker and self.manager:
                    # 1. Update touch sensor readings and timestamp history
                    self.tracker.update()

                    # 2. Get the relevant touch count
                    touch_count = self.tracker.get_touch_count_last_hour()

                    # 3. Update the state (sad/glad) based on the count
                    self.manager.update_state(touch_count)

                    # 4. Prepare stats for broadcasting
                    stats: Dict[str, Union[bool, int]] = {
                        "is_glad": self.manager.is_glad,
                        "touch_count_last_hour": touch_count,
                        "touch_threshold": self.manager.touch_threshold,
                        "total_touches": self.tracker.get_total_touches(),
                        "today_touches": self.tracker.get_today_touches(),
                    }
                    # 5. Broadcast stats via WebSocket
                    await broadcast_stats(stats)

                # Wait before next cycle
                await asyncio.sleep(self.config.update_interval_sec)
            except Exception as e:
                logger.error(f"Error in sensor monitoring task: {e}")
                await asyncio.sleep(5)  # Wait before retrying after an error

        logger.info("Sensor monitoring task stopped")

    def run(self) -> None:
        """Run the FastAPI application using Uvicorn."""
        logger.info(f"Server starting on {self.config.host}:{self.config.port}")
        uvicorn.run(
            self.app,
            host=self.config.host,
            port=self.config.port,
            log_level=self.config.log_level,
        )
