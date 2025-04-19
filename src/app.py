#!/usr/bin/env python3
"""
Touch Companion Application Module.

Contains the main application class that drives the Touch Companion system.
"""

import time
import asyncio
import logging
import json  # Added for state persistence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, Optional, Union

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.config import AppConfig
from src.hardware.led_strip import LedStrip
from src.touch_tracker import TouchTracker
from src.state_manager import StateManager
from src.camera_manager import CameraManager
from src.web import routes as web_routes
from src.web.routes import broadcast_stats, broadcast_api_response

# Configure logger
logger = logging.getLogger("touch_companion")

# Define state file path (adjust as needed)
STATE_FILE = Path(__file__).parent.parent / "data" / "app_state.json"


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
        self.camera_manager: Optional[CameraManager] = None
        self.background_task_running = False
        self._state_file_path = STATE_FILE  # Store state file path

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
            # Ensure data directory exists for state file
            self._state_file_path.parent.mkdir(parents=True, exist_ok=True)

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

            # Initialize Camera Manager if enabled
            if self.config.camera_enabled:
                self.camera_manager = CameraManager(
                    api_url=self.config.ya_api_url,
                    min_interval_sec=self.config.cam_interval,
                    response_display_time=self.config.response_display_time,
                )
                logger.info("Camera manager initialized")

                # Register the API response broadcast callback
                self.camera_manager.register_response_callback(broadcast_api_response)

                # Set touch callback if tracker is available
                if self.tracker:
                    self.tracker.set_touch_callback(self._on_touch)
                    logger.info("Touch callback registered")
            else:
                logger.info("Camera functionality is disabled in configuration")

            # Load previous state if available
            self._load_state()

            # Start the background task
            asyncio.create_task(self._sensor_monitor_task())

        except ImportError as e:
            logger.error(f"Import error during startup: {e}")
            logger.error(
                "Ensure required libraries are installed (smbus2, pi5neo, fastapi, uvicorn, opencv-python, aiohttp)"
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
        # Save state on shutdown
        self._save_state()

    async def _on_touch(self) -> None:
        """Handle touch events for camera integration."""
        if not self.camera_manager:
            return

        try:
            # Process the touch event in the camera manager
            was_processed = await self.camera_manager.process_touch_event()
            if was_processed:
                logger.info("Touch triggered camera capture")
        except Exception as e:
            logger.error(f"Error in touch callback: {e}", exc_info=True)

    async def _sensor_monitor_task(self) -> None:
        """Run the core sensor reading and state update logic in the background."""
        logger.info("Sensor monitoring task started")
        while self.background_task_running:
            try:
                if self.tracker and self.manager:
                    # 1. Update touch sensor readings and timestamp history
                    await self.tracker.update()

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

                    # 6. Save current state periodically (every minute)
                    if int(time.time()) % 60 == 0:
                        self._save_state()

                # Wait before next cycle
                await asyncio.sleep(self.config.update_interval_sec)
            except Exception as e:
                logger.error(f"Error in sensor monitoring task: {e}")
                await asyncio.sleep(5)  # Wait before retrying after an error

        logger.info("Sensor monitoring task stopped")

    def _save_state(self) -> None:
        """Save the current application state to a file."""
        try:
            state_data = {}

            if self.tracker:
                state_data["tracker"] = self.tracker.get_state()

            if self.manager:
                state_data["manager"] = self.manager.get_state()

            if self.camera_manager:
                state_data["camera"] = self.camera_manager.get_state()

            with open(self._state_file_path, "w") as f:
                json.dump(state_data, f, indent=4)
            logger.debug(f"Application state saved to {self._state_file_path}")
        except AttributeError as e:
            logger.warning(
                f"Could not get state from components (might still be initializing): {e}"
            )
        except IOError as e:
            logger.error(
                f"Failed to save application state to {self._state_file_path}: {e}"
            )
        except Exception as e:
            logger.error(f"Unexpected error saving state: {e}", exc_info=True)

    def _load_state(self) -> None:
        """Load application state from a file if it exists."""
        if not self._state_file_path.exists():
            logger.info("No previous state file found, starting fresh.")
            return

        try:
            with open(self._state_file_path, "r") as f:
                state_data = json.load(f)

            if "tracker" in state_data and self.tracker:
                self.tracker.load_state(state_data["tracker"])
                logger.info("Loaded state for TouchTracker")

            if "manager" in state_data and self.manager:
                self.manager.load_state(state_data["manager"])
                logger.info("Loaded state for StateManager")

            if "camera" in state_data and self.camera_manager:
                self.camera_manager.load_state(state_data["camera"])
                logger.info("Loaded state for CameraManager")

            logger.info(
                f"Application state successfully loaded from {self._state_file_path}"
            )

        except (IOError, json.JSONDecodeError) as e:
            logger.error(
                f"Failed to load application state from {self._state_file_path}: {e}"
            )
        except AttributeError as e:
            logger.warning(f"Could not load state into components: {e}")
        except Exception as e:
            logger.error(f"Unexpected error loading state: {e}", exc_info=True)

    def run(self) -> None:
        """Run the FastAPI application using Uvicorn."""
        logger.info(f"Server starting on {self.config.host}:{self.config.port}")
        uvicorn.run(
            self.app,
            host=self.config.host,
            port=self.config.port,
            log_level=self.config.log_level,
        )
