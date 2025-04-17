import time
import sys
import os

# Adjust path to import from parent directory's hardware module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from hardware.led_strip import LedStrip
from new_logic.touch_tracker import TouchTracker
from new_logic.state_manager import StateManager

# --- Configuration ---
# MPR121 Sensor Config
I2C_ADDRESS = 0x5A
I2C_BUS = 1
HISTORY_DURATION_SEC = 3600 # 1 hour

# LED Strip Config
# IMPORTANT: Update '/dev/spidev0.0' if your SPI device is different
LED_DEVICE = '/dev/spidev0.0'
NUM_LEDS = 280 # Adjust to your LED strip length
LED_FREQUENCY = 800 # Standard for WS2812b

# State Logic Config
TOUCH_THRESHOLD = 20 # Touches in the last hour to trigger GLAD state
UPDATE_INTERVAL_SEC = 0.1 # How often to check the sensor and update state

# --- Main Application ---
def main():
    leds = None # Initialize to None for cleanup check
    try:
        print("Initializing LED strip...")
        # Ensure the SPI device exists (basic check)
        if not os.path.exists(LED_DEVICE):
             print(f"Error: LED device {LED_DEVICE} not found.")
             print("Please check your SPI configuration and device path.")
             # You might need to enable SPI via raspi-config
             return # Exit if device not found

        leds = LedStrip(device=LED_DEVICE, num_leds=NUM_LEDS, frequency=LED_FREQUENCY)
        print("Initializing Touch Tracker...")
        tracker = TouchTracker(i2c_address=I2C_ADDRESS, i2c_bus=I2C_BUS, history_duration_sec=HISTORY_DURATION_SEC)
        print("Initializing State Manager...")
        manager = StateManager(leds, touch_threshold=TOUCH_THRESHOLD)

        print("\n--- Running Touch Companion (New Logic) ---")
        print(f"Monitoring touches on I2C bus {I2C_BUS}, address {I2C_ADDRESS}.")
        print(f"State changes based on >= {TOUCH_THRESHOLD} touches in the last {HISTORY_DURATION_SEC / 60:.0f} minutes.")
        print("Press Ctrl+C to exit.")

        while True:
            # 1. Update touch sensor readings and timestamp history
            tracker.update()

            # 2. Get the relevant touch count
            touch_count = tracker.get_touch_count_last_hour()

            # 3. Update the state (sad/glad) based on the count
            manager.update_state(touch_count)

            # 4. Wait before next cycle
            time.sleep(UPDATE_INTERVAL_SEC)

    except KeyboardInterrupt:
        print("\nCtrl+C detected. Exiting gracefully...")
    except ImportError as e:
        print(f"\nImport Error: {e}")
        print("Please ensure necessary libraries (e.g., smbus2, pi5neo) are installed.")
        print("Try running: pip install -r requirements-base.txt")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
    finally:
        if leds:
            print("Cleaning up LEDs...")
            leds.clear() # Turn off LEDs on exit
        print("Application stopped.")

if __name__ == "__main__":
    main()