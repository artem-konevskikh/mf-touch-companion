#!/usr/bin/env python3
"""
Touch Tracker Module.

Tracks touch events from the MPR121 sensor and stores timestamps for historical analysis.
"""

import logging
import time
from collections import deque
from typing import Deque, List, Optional

from src.hardware.mpr121 import MPR121TouchSensor

# Configure logger
logger = logging.getLogger("touch_companion.touch_tracker")


class TouchTracker:
    """Tracks touch events from the MPR121 sensor and stores timestamps."""

    def __init__(
        self,
        i2c_address: int = 0x5A,
        i2c_bus: int = 1,
        history_duration_sec: int = 3600,
    ):
        """Initialize the TouchTracker.

        Args:
            i2c_address: The I2C address of the MPR121 sensor
            i2c_bus: The I2C bus number
            history_duration_sec: The duration (in seconds) to keep touch history (default: 1 hour)
        """
        self.sensor: Optional[MPR121TouchSensor] = None
        self.history_duration = history_duration_sec
        self.touch_timestamps: Deque[float] = deque()
        self._last_touch_status: List[bool] = [False] * 12

        try:
            self.sensor = MPR121TouchSensor(i2c_address, i2c_bus)
            logger.info(
                f"MPR121 touch sensor initialized on bus {i2c_bus}, address {hex(i2c_address)}"
            )
        except Exception as e:
            logger.error(f"Error initializing MPR121 sensor: {e}", exc_info=True)
            # Sensor init failed, but we'll continue with self.sensor as None

    def update(self) -> None:
        """Read the sensor and record timestamps for new touch events."""
        if not self.sensor:
            return  # Do nothing if sensor failed to initialize

        try:
            current_status = self.sensor.read_touch_status()
        except Exception as e:
            logger.error(f"Error reading touch status: {e}")
            return  # Skip update if reading fails

        current_time = time.time()

        for i in range(12):
            # Detect a rising edge (touch start)
            if current_status[i] and not self._last_touch_status[i]:
                self.touch_timestamps.append(current_time)
                logger.debug(f"Touch detected on electrode {i}")

        self._last_touch_status = current_status

        # Prune old timestamps
        self._prune_history(current_time)

    def _prune_history(self, current_time: float) -> None:
        """Remove timestamps older than the history duration.

        Args:
            current_time: The current timestamp to compare against
        """
        while self.touch_timestamps and (
            current_time - self.touch_timestamps[0] > self.history_duration
        ):
            self.touch_timestamps.popleft()

    def get_touch_count_last_hour(self) -> int:
        """Return the number of touches recorded within the history duration.

        Returns:
            The count of touch events within the history window
        """
        # Ensure history is pruned before counting
        current_time = time.time()
        self._prune_history(current_time)
        return len(self.touch_timestamps)


# Example Usage (for testing)
if __name__ == "__main__":
    # Configure logging for standalone testing
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger.info("Touch Tracker test mode. Press Ctrl+C to exit.")

    tracker = TouchTracker()

    try:
        while True:
            tracker.update()
            count = tracker.get_touch_count_last_hour()
            logger.info(f"Touches in the last hour: {count}")
            time.sleep(0.1)  # Check sensor periodically
    except KeyboardInterrupt:
        logger.info("Test terminated by user")
    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
