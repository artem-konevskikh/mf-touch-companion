"""
Core Sensor Module for Touch Companion Application

This module interfaces with the MPR121 touch sensor to:
- Detect touch events
- Measure touch duration
- Assign sensor IDs
- Pass touch data to the database module
- Handle sensor initialization and error recovery

Note: This module is designed to work with the custom MPR121 interface.
"""

import asyncio
import logging
import time
from typing import Dict, Set, Callable
from datetime import datetime

from src.hardware.mpr121_interface import MPR121Sensor
from src.modules.database import db
from src.modules.emotional_state import EmotionalStateEngine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("data/sensor.log"), logging.StreamHandler()],
)
logger = logging.getLogger("sensor")


class TouchSensorManager:
    """Manages the MPR121 touch sensor and processes touch events."""

    def __init__(self, emotional_state_engine: EmotionalStateEngine):
        """
        Initialize the touch sensor manager.

        Args:
            emotional_state_engine: Reference to the emotional state engine
        """
        self.sensor = None
        self.running = False
        self.active_touches: Dict[int, float] = {}  # sensor_id -> start_time
        self.emotional_state_engine = emotional_state_engine
        self.callbacks: Set[Callable] = set()
        self.error_count = 0
        self.max_errors = 5
        self.error_cooldown = 10  # seconds
        self.last_error_time = 0

    async def initialize(self) -> bool:
        """
        Initialize the MPR121 touch sensor.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Initialize your custom MPR121 sensor interface
            self.sensor = MPR121Sensor()
            await asyncio.to_thread(self.sensor.initialize)
            self.error_count = 0
            logger.info("Touch sensor initialized successfully")
            return True
        except Exception as e:
            self.error_count += 1
            logger.error(f"Failed to initialize touch sensor: {str(e)}")
            return False

    async def start(self) -> None:
        """Start the touch sensor processing loop."""
        if self.running:
            return

        self.running = True

        if not self.sensor and not await self.initialize():
            logger.error("Cannot start sensor processing - initialization failed")
            self.running = False
            return

        logger.info("Starting touch sensor processing loop")
        asyncio.create_task(self._processing_loop())

    async def stop(self) -> None:
        """Stop the touch sensor processing loop."""
        logger.info("Stopping touch sensor processing")
        self.running = False

        # Process any remaining active touches
        current_time = time.time()
        for sensor_id, start_time in list(self.active_touches.items()):
            await self._process_touch_end(sensor_id, start_time, current_time)

        self.active_touches.clear()

    def register_callback(self, callback: Callable) -> None:
        """
        Register a callback function to be called when touch events occur.

        The callback will receive a dictionary with touch event details.

        Args:
            callback: Function to call with touch event data
        """
        self.callbacks.add(callback)

    def unregister_callback(self, callback: Callable) -> None:
        """Remove a previously registered callback."""
        if callback in self.callbacks:
            self.callbacks.remove(callback)

    async def _processing_loop(self) -> None:
        """Main processing loop for touch sensor events."""
        while self.running:
            try:
                # Read current touch state from sensor
                touch_state = await asyncio.to_thread(self.sensor.read_touch_state)
                current_time = time.time()

                # Process touch state changes
                for sensor_id in range(12):  # MPR121 has 12 channels
                    is_touched = bool((touch_state >> sensor_id) & 1)

                    # New touch started
                    if is_touched and sensor_id not in self.active_touches:
                        self.active_touches[sensor_id] = current_time
                        logger.debug(f"Touch started on sensor {sensor_id}")

                    # Touch ended
                    elif not is_touched and sensor_id in self.active_touches:
                        start_time = self.active_touches.pop(sensor_id)
                        await self._process_touch_end(
                            sensor_id, start_time, current_time
                        )

                # Short delay to prevent CPU hogging
                await asyncio.sleep(0.01)

            except Exception as e:
                current_time = time.time()
                # Handle errors with exponential backoff
                if current_time - self.last_error_time < self.error_cooldown:
                    self.error_count += 1
                else:
                    self.error_count = 1

                self.last_error_time = current_time

                logger.error(f"Error in touch sensor processing loop: {str(e)}")

                if self.error_count > self.max_errors:
                    logger.error(
                        "Too many consecutive errors, attempting sensor reinitialize"
                    )
                    # Try to reinitialize the sensor
                    if await self.initialize():
                        logger.info("Sensor reinitialized successfully")
                    else:
                        # If reinitialization fails, pause processing for a while
                        await asyncio.sleep(self.error_cooldown)
                else:
                    # Brief pause before continuing
                    await asyncio.sleep(0.1)

    async def _process_touch_end(
        self, sensor_id: int, start_time: float, end_time: float
    ) -> None:
        """
        Process the end of a touch event.

        Args:
            sensor_id: ID of the sensor that was touched
            start_time: Time when touch started (seconds)
            end_time: Time when touch ended (seconds)
        """
        duration_ms = int((end_time - start_time) * 1000)
        logger.debug(f"Touch ended on sensor {sensor_id}, duration: {duration_ms}ms")

        # Get current emotional state
        state = await self.emotional_state_engine.get_current_state()

        # Store in database
        try:
            touch_id = await db.add_touch_event(sensor_id, duration_ms, state)

            # Prepare event data for callbacks
            event_data = {
                "id": touch_id,
                "sensor_id": sensor_id,
                "timestamp": datetime.now().isoformat(),
                "duration_ms": duration_ms,
                "state": state,
            }

            # Notify emotional state engine
            await self.emotional_state_engine.process_touch_event(duration_ms)

            # Call registered callbacks
            for callback in self.callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(event_data)
                    else:
                        callback(event_data)
                except Exception as e:
                    logger.error(f"Error in touch event callback: {str(e)}")

        except Exception as e:
            logger.error(f"Error saving touch event to database: {str(e)}")

    def get_sensor_status(self) -> Dict:
        """
        Get the current status of the touch sensor.

        Returns:
            Dictionary with sensor status information
        """
        return {
            "initialized": self.sensor is not None,
            "running": self.running,
            "active_touches": len(self.active_touches),
            "error_count": self.error_count,
        }
