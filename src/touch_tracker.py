#!/usr/bin/env python3
"""
Touch Tracker Module.

Tracks touch events from the MPR121 sensor and stores timestamps for historical analysis.
"""

import logging
import time
from collections import deque
from datetime import date  # Added datetime for state serialization
from typing import Deque, Dict, List, Optional, Callable, Awaitable

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

        # Track total touches and daily touches
        self.total_touches: int = 0
        self.daily_touches: Dict[date, int] = {}
        self._current_date: date = date.today()

        # Callback for touch events, to be set by camera integration
        self._touch_callback: Optional[Callable[[], Awaitable[None]]] = None

        try:
            self.sensor = MPR121TouchSensor(i2c_address, i2c_bus)
            logger.info(
                f"MPR121 touch sensor initialized on bus {i2c_bus}, address {hex(i2c_address)}"
            )
        except Exception as e:
            logger.error(f"Error initializing MPR121 sensor: {e}", exc_info=True)
            # Sensor init failed, but we'll continue with self.sensor as None

    def set_touch_callback(self, callback: Callable[[], Awaitable[None]]) -> None:
        """Set a callback function to be called when a touch is detected.

        Args:
            callback: Async function to call when touch is detected
        """
        self._touch_callback = callback
        logger.info("Touch callback set")

    async def update(self) -> None:
        """Read the sensor and record timestamps for new touch events."""
        if not self.sensor:
            return  # Do nothing if sensor failed to initialize

        try:
            current_status = self.sensor.read_touch_status()
        except Exception as e:
            logger.error(f"Error reading touch status: {e}")
            return  # Skip update if reading fails

        current_time = time.time()
        today = date.today()

        # Check if date has changed - if so, update the current date
        if today != self._current_date:
            self._current_date = today

        # Initialize today's count if not present
        if today not in self.daily_touches:
            self.daily_touches[today] = 0

        touch_detected = False
        for i in range(12):
            # Detect a rising edge (touch start)
            if current_status[i] and not self._last_touch_status[i]:
                self.touch_timestamps.append(current_time)

                # Update touch counts
                self.total_touches += 1
                self.daily_touches[today] += 1

                touch_detected = True
                logger.debug(f"Touch detected on electrode {i}")

        if touch_detected:
            logger.debug(
                f"Total touches: {self.total_touches}, Today: {self.daily_touches[today]}"
            )

            # Call touch callback if set
            if self._touch_callback:
                try:
                    await self._touch_callback()
                except Exception as e:
                    logger.error(f"Error in touch callback: {e}", exc_info=True)

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

        # Also prune old daily counts (keep only the last 30 days)
        today = date.today()
        keys_to_remove = []
        for day in self.daily_touches.keys():
            if (today - day).days > 30:
                keys_to_remove.append(day)

        for day in keys_to_remove:
            del self.daily_touches[day]

    def get_touch_count_last_hour(self) -> int:
        """Return the number of touches recorded within the history duration.

        Returns:
            The count of touch events within the history window
        """
        # Ensure history is pruned before counting
        current_time = time.time()
        self._prune_history(current_time)
        return len(self.touch_timestamps)

    def get_total_touches(self) -> int:
        """Return the total number of touches recorded since startup.

        Returns:
            The total count of touch events
        """
        return self.total_touches

    def get_today_touches(self) -> int:
        """Return the number of touches recorded today.

        Returns:
            The count of touch events for the current day
        """
        today = date.today()
        return self.daily_touches.get(today, 0)

    def get_state(self) -> Dict:
        """Return the current state of the tracker for persistence."""
        # Convert date keys to ISO format strings for JSON serialization
        serializable_daily_touches = {
            day.isoformat(): count for day, count in self.daily_touches.items()
        }
        return {
            "total_touches": self.total_touches,
            "daily_touches": serializable_daily_touches,
            "touch_timestamps": list(self.touch_timestamps),  # Convert deque to list
            "_current_date": self._current_date.isoformat(),
            "_last_touch_status": self._last_touch_status,
        }

    def load_state(self, state_data: Dict) -> None:
        """Load the tracker state from a dictionary."""
        try:
            self.total_touches = state_data.get("total_touches", 0)

            # Convert ISO format strings back to date objects
            loaded_daily_touches = state_data.get("daily_touches", {})
            self.daily_touches = {
                date.fromisoformat(day_str): count
                for day_str, count in loaded_daily_touches.items()
            }

            # Convert list back to deque
            self.touch_timestamps = deque(state_data.get("touch_timestamps", []))

            # Load current date and last touch status
            current_date_str = state_data.get("_current_date")
            if current_date_str:
                self._current_date = date.fromisoformat(current_date_str)
            else:
                self._current_date = date.today()  # Default if not found

            self._last_touch_status = state_data.get("_last_touch_status", [False] * 12)

            # Prune history based on loaded timestamps and current time
            self._prune_history(time.time())

            logger.info("TouchTracker state loaded successfully.")
        except Exception as e:
            logger.error(f"Error loading TouchTracker state: {e}", exc_info=True)


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
        import asyncio

        async def main():
            while True:
                await tracker.update()
                count = tracker.get_touch_count_last_hour()
                logger.info(f"Touches in the last hour: {count}")
                await asyncio.sleep(0.1)  # Check sensor periodically

        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Test terminated by user")
    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
