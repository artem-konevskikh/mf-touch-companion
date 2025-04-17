import time
import sys
import os
import asyncio
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

# Adjust path to import from parent directory's hardware module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from hardware.led_strip import LedStrip
from new_logic.touch_tracker import TouchTracker
from new_logic.state_manager import StateManager
from new_logic.web import routes as web_routes  # Import web routes
from new_logic.web.routes import broadcast_stats  # Import broadcast function

# --- Configuration ---
# MPR121 Sensor Config
I2C_ADDRESS = 0x5A
I2C_BUS = 1
HISTORY_DURATION_SEC = 3600  # 1 hour

# LED Strip Config
# IMPORTANT: Update '/dev/spidev0.0' if your SPI device is different
LED_DEVICE = "/dev/spidev0.0"
NUM_LEDS = 280  # Adjust to your LED strip length
LED_FREQUENCY = 800  # Standard for WS2812b

# State Logic Config
TOUCH_THRESHOLD = 20  # Touches in the last hour to trigger GLAD state
UPDATE_INTERVAL_SEC = 0.1  # How often to check the sensor and update state

# --- Global Variables (for sharing between background task and FastAPI) ---
leds: LedStrip | None = None
tracker: TouchTracker | None = None
manager: StateManager | None = None
background_task_running = True


# --- Background Task for Sensor Monitoring ---
async def sensor_monitor_task():
    """Runs the core sensor reading and state update logic in the background."""
    global leds, tracker, manager, background_task_running
    print("Starting sensor monitoring task...")
    while background_task_running:
        try:
            if tracker and manager:
                # 1. Update touch sensor readings and timestamp history
                tracker.update()

                # 2. Get the relevant touch count
                touch_count = tracker.get_touch_count_last_hour()

                # 3. Update the state (sad/glad) based on the count
                manager.update_state(touch_count)

                # 4. Prepare stats for broadcasting
                stats = {
                    "is_glad": manager.is_glad,
                    "touch_count_last_hour": touch_count,
                    "touch_threshold": manager.touch_threshold,
                }
                # 5. Broadcast stats via WebSocket
                await broadcast_stats(stats)

            # Wait before next cycle
            await asyncio.sleep(UPDATE_INTERVAL_SEC)
        except Exception as e:
            print(f"Error in sensor_monitor_task: {e}")
            await asyncio.sleep(5)  # Wait before retrying after an error
    print("Sensor monitoring task stopped.")


# --- FastAPI Application Setup ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    global leds, tracker, manager, background_task_running
    print("Application startup...")
    background_task_running = True
    try:
        print("Initializing LED strip...")
        if not os.path.exists(LED_DEVICE):
            print(f"Error: LED device {LED_DEVICE} not found. Check config.")
            # In a real app, might raise an exception or handle differently
        else:
            leds = LedStrip(
                device=LED_DEVICE, num_leds=NUM_LEDS, frequency=LED_FREQUENCY
            )

        print("Initializing Touch Tracker...")
        tracker = TouchTracker(
            i2c_address=I2C_ADDRESS,
            i2c_bus=I2C_BUS,
            history_duration_sec=HISTORY_DURATION_SEC,
        )

        if leds:
            print("Initializing State Manager...")
            manager = StateManager(leds, touch_threshold=TOUCH_THRESHOLD)
        else:
            print("Skipping State Manager initialization (LEDs not available).")

        # Start the background task
        asyncio.create_task(sensor_monitor_task())
        print("Background sensor task started.")

    except ImportError as e:
        print(f"\nImport Error during startup: {e}")
        print("Ensure libraries (smbus2, pi5neo, fastapi, uvicorn) are installed.")
        print("Try running: pip install -r requirements-base.txt")
        # Optionally exit or prevent app start
    except Exception as e:
        print(f"\nAn unexpected error occurred during startup: {e}")
        # Optionally exit or prevent app start

    yield  # Application runs here

    # Shutdown logic
    print("\nApplication shutdown...")
    background_task_running = False  # Signal background task to stop
    # Give the task a moment to finish gracefully (optional)
    await asyncio.sleep(UPDATE_INTERVAL_SEC * 2)
    if leds:
        print("Cleaning up LEDs...")
        leds.clear()  # Turn off LEDs on exit
    print("Application stopped.")


app = FastAPI(lifespan=lifespan)

# Mount static files (for CSS/JS)
# Ensure the path is correct relative to where this script is run from
static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "web/static"))
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
else:
    print(f"Warning: Static directory not found at {static_dir}")

# Include web routes
app.include_router(web_routes.router)

# --- Main Execution --- (Runs the Uvicorn server)
if __name__ == "__main__":
    print("\n--- Starting Touch Companion Web Server (New Logic) ---")
    print(f"Access the UI at http://<your-pi-ip>:8000")
    # Use host="0.0.0.0" to allow access from other devices on the network
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
