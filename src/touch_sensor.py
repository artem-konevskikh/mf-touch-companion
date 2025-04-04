"""
Core Sensor Module for touch sensor companion device.

This module interfaces with the MPR121 touch sensor and processes touch events.
"""

import logging
import time
import threading
from typing import Callable, Optional, List

from src.database import Database, TouchEvent

# Import the provided MPR121TouchSensor class
from src.hardware.mpr121 import MPR121TouchSensor

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class TouchSensorService:
    """Service for interfacing with the MPR121 touch sensor."""

    def __init__(
        self,
        database: Database,
        i2c_address: int = 0x5A,
        i2c_bus: int = 1,
        update_interval: float = 0.05,
        callback: Optional[Callable[[TouchEvent], None]] = None,
    ) -> None:
        """Initialize the touch sensor service.

        Args:
            database: The database instance for storing touch events
            i2c_address: The I2C address of the MPR121 sensor
            i2c_bus: The I2C bus number
            update_interval: The interval in seconds between sensor updates
            callback: Optional callback function for touch events
        """
        self.database = database
        self.update_interval = update_interval
        self.callback = callback

        # Initialize sensor
        self.sensor = MPR121TouchSensor(i2c_address=i2c_address, i2c_bus=i2c_bus)

        # For tracking the currently active touches and managing service
        self.active_touches = [False] * 12
        self.touch_start_times = [0.0] * 12
        self._running = False
        self._thread: Optional[threading.Thread] = None

        logger.info("Touch sensor service initialized")

    def start(self) -> None:
        """Start the touch sensor service in a separate thread."""
        if self._running:
            logger.warning("Touch sensor service is already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_service, daemon=True)
        self._thread.start()
        logger.info("Touch sensor service started")

    def stop(self) -> None:
        """Stop the touch sensor service."""
        if not self._running:
            logger.warning("Touch sensor service is not running")
            return

        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            logger.info("Touch sensor service stopped")

    def _run_service(self) -> None:
        """Main loop for the touch sensor service."""
        error_count = 0
        max_errors = 5
        retry_delay = 1.0

        while self._running:
            try:
                self._process_touch_events()
                error_count = 0  # Reset error count on success
                time.sleep(self.update_interval)

            except Exception as e:
                error_count += 1
                logger.error(f"Error in touch sensor service: {e}")

                if error_count >= max_errors:
                    logger.critical(
                        f"Too many errors ({error_count}), restarting sensor"
                    )
                    try:
                        # Reinitialize the sensor
                        self.sensor = MPR121TouchSensor(
                            i2c_address=self.sensor.i2c_address,
                            i2c_bus=self.sensor.bus.bus,
                        )
                        error_count = 0  # Reset error count after reinitializing
                    except Exception as init_error:
                        logger.critical(f"Failed to reinitialize sensor: {init_error}")

                # Wait before retrying
                time.sleep(retry_delay)

    def _process_touch_events(self) -> None:
        """Process touch events from the sensor."""
        # Update the sensor
        self.sensor.update()

        # Get the current touch status
        current_touches = self.sensor.current_touches
        current_time = time.time()

        # Process each electrode
        for i in range(12):
            # Touch start (not previously touched, but now touched)
            if not self.active_touches[i] and current_touches[i]:
                self.active_touches[i] = True
                self.touch_start_times[i] = current_time
                logger.debug(f"Touch started on electrode {i}")

            # Touch end (previously touched, but now released)
            elif self.active_touches[i] and not current_touches[i]:
                self.active_touches[i] = False
                duration = current_time - self.touch_start_times[i]

                # Create and store touch event
                event = TouchEvent(
                    sensor_id=i, timestamp=current_time, duration=duration
                )

                # Add to database
                try:
                    self.database.add_touch_event(event)
                    logger.debug(
                        f"Touch event stored: sensor={i}, duration={duration:.3f}s"
                    )

                    # Call the callback if provided
                    if self.callback:
                        self.callback(event)

                except Exception as e:
                    logger.error(f"Failed to store touch event: {e}")

    def get_active_electrodes(self) -> List[int]:
        """Get a list of currently active (touched) electrodes.

        Returns:
            A list of electrode indices that are currently being touched
        """
        return [i for i, touched in enumerate(self.active_touches) if touched]

    def get_sensor_status(self) -> dict:
        """Get the current status of the touch sensor.

        Returns:
            A dictionary with sensor status information
        """
        return {
            "active_electrodes": self.get_active_electrodes(),
            "touch_count": self.sensor.get_touch_count(),
            "average_duration": self.sensor.get_average_touch_duration(),
        }
