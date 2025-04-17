import time
from collections import deque
from src.hardware.mpr121 import MPR121TouchSensor


class TouchTracker:
    """Tracks touch events from the MPR121 sensor and stores timestamps."""

    def __init__(self, i2c_address=0x5A, i2c_bus=1, history_duration_sec=3600):
        """Initialize the TouchTracker.

        Args:
            i2c_address: The I2C address of the MPR121 sensor.
            i2c_bus: The I2C bus number.
            history_duration_sec: The duration (in seconds) to keep touch history (default: 1 hour).
        """
        try:
            self.sensor = MPR121TouchSensor(i2c_address, i2c_bus)
        except Exception as e:
            print(f"Error initializing MPR121 sensor: {e}")
            # Consider adding fallback or error handling if sensor init fails
            self.sensor = None  # Indicate sensor is not available

        self.history_duration = history_duration_sec
        # Use a deque for efficient addition and removal from both ends
        self.touch_timestamps = deque()
        self._last_touch_status = [False] * 12

    def update(self):
        """Reads the sensor and records timestamps for new touch events."""
        if not self.sensor:
            # print("Sensor not available, skipping update.")
            return  # Do nothing if sensor failed to initialize

        try:
            current_status = self.sensor.read_touch_status()
        except Exception as e:
            print(f"Error reading touch status: {e}")
            return  # Skip update if reading fails

        current_time = time.time()

        for i in range(12):
            # Detect a rising edge (touch start)
            if current_status[i] and not self._last_touch_status[i]:
                self.touch_timestamps.append(current_time)
                print(
                    f"Touch detected on electrode {i} at {current_time}"
                )  # Optional: for debugging

        self._last_touch_status = current_status

        # Prune old timestamps
        self._prune_history(current_time)

    def _prune_history(self, current_time):
        """Removes timestamps older than the history duration."""
        while self.touch_timestamps and (
            current_time - self.touch_timestamps[0] > self.history_duration
        ):
            self.touch_timestamps.popleft()

    def get_touch_count_last_hour(self):
        """Returns the number of touches recorded within the history duration."""
        # Ensure history is pruned before counting
        current_time = time.time()
        self._prune_history(current_time)
        return len(self.touch_timestamps)


# Example Usage (for testing)
if __name__ == "__main__":
    tracker = TouchTracker()
    print("Touch Tracker initialized. Press Ctrl+C to exit.")

    try:
        while True:
            tracker.update()
            count = tracker.get_touch_count_last_hour()
            print(f"Touches in the last hour: {count}")
            time.sleep(0.1)  # Check sensor periodically
    except KeyboardInterrupt:
        print("\nExiting.")
    except Exception as e:
        print(f"An error occurred: {e}")
