"""
Main application module for touch sensor companion device.

This module integrates all components of the application.
"""

import argparse
import logging
import signal
import sys
import time
from pathlib import Path
from typing import Any, Optional

from src.database import Database
from src.touch_sensor import TouchSensorService
from src.emotional_state_engine import EmotionalStateEngine
from src.webapp.app import WebApp
from src.hardware.led_strip import LedStrip

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path.home() / "touch_companion.log"),
    ],
)
logger = logging.getLogger(__name__)


class TouchCompanionApp:
    """Main application class for the touch sensor companion device."""
    def __init__(
        self,
        data_dir: Path = Path(__file__).parent.parent / "data",
        led_device: str = "/dev/spidev0.0",
        led_count: int = 30,
        led_frequency: int = 800,
        i2c_address: int = 0x5A,
        i2c_bus: int = 1,
        host: str = "0.0.0.0",
        port: int = 8000,
    ) -> None:
        """Initialize the touch companion application.

        Args:
            data_dir: Directory for storing data files
            led_device: Device path for the LED strip
            led_count: Number of LEDs in the strip
            led_frequency: Frequency for the LED strip
            i2c_address: I2C address for the MPR121 sensor
            i2c_bus: I2C bus number
            host: Host to bind the web server to
            port: Port for the web server
        """
        self.data_dir = data_dir
        self.led_device = led_device
        self.led_count = led_count
        self.led_frequency = led_frequency
        self.i2c_address = i2c_address
        self.i2c_bus = i2c_bus
        self.host = host
        self.port = port

        # Create data directory if it doesn't exist
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.database: Optional[Database] = None
        self.led_strip: Optional[LedStrip] = None
        self.touch_sensor: Optional[TouchSensorService] = None
        self.emotional_state_engine: Optional[EmotionalStateEngine] = None
        self.webapp: Optional[WebApp] = None

        self._running = False

        # Set up signal handlers
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        logger.info("Touch companion application initialized")

    def _handle_signal(self, sig: int, _: Any) -> None:
        """Handle termination signals.

        Args:
            sig: Signal number
        """
        logger.info(f"Received signal {sig}, shutting down")
        self.stop()
        sys.exit(0)

    def start(self) -> None:
        """Start all components of the application."""
        if self._running:
            logger.warning("Application is already running")
            return

        logger.info("Starting touch companion application")
        self._running = True

        try:
            # Initialize database first
            logger.info("Initializing database")
            self.database = Database(db_path=self.data_dir / "touch_data.db")

            # Initialize LED strip
            logger.info("Initializing LED strip")
            self.led_strip = LedStrip(
                device=self.led_device,
                num_leds=self.led_count,
                frequency=self.led_frequency,
            )

            # Initialize emotional state engine
            logger.info("Initializing emotional state engine")
            self.emotional_state_engine = EmotionalStateEngine(
                database=self.database, led_strip=self.led_strip
            )

            # Set up touch sensor callback
            def touch_callback(event):
                logger.debug(
                    f"Touch event: sensor={event.sensor_id}, duration={event.duration:.3f}s"
                )
                # Notify all connected web clients about the new touch event
                from src.webapp.routes.api import notify_touch_event
                notify_touch_event()

            # Initialize touch sensor service
            logger.info("Initializing touch sensor service")
            self.touch_sensor = TouchSensorService(
                database=self.database,
                i2c_address=self.i2c_address,
                i2c_bus=self.i2c_bus,
                callback=touch_callback,
            )

            # Initialize web application
            logger.info("Initializing web application")
            self.webapp = WebApp(
                database=self.database,
                emotional_state_engine=self.emotional_state_engine,
                host=self.host,
                port=self.port,
            )

            # Start components
            logger.info("Starting touch sensor service")
            self.touch_sensor.start()

            logger.info("Starting emotional state engine")
            self.emotional_state_engine.start()

            logger.info("Starting web application")
            self.webapp.run()  # This will block until the application exits

        except Exception as e:
            logger.error(f"Error starting application: {e}", exc_info=True)
            self.stop()
            raise

    def stop(self) -> None:
        """Stop all components of the application."""
        if not self._running:
            return

        logger.info("Stopping touch companion application")

        try:
            # Stop components in reverse order
            if self.touch_sensor:
                logger.info("Stopping touch sensor service")
                self.touch_sensor.stop()

            if self.emotional_state_engine:
                logger.info("Stopping emotional state engine")
                self.emotional_state_engine.stop()

            # Ensure LED strip is properly cleared
            if self.led_strip:
                logger.info("Clearing LED strip")
                # Now clear the LEDs
                self.led_strip.clear()

            # Web app doesn't need explicit stopping as it will be terminated with the process

            self._running = False
            logger.info("Application stopped")

        except Exception as e:
            logger.error(f"Error stopping application: {e}", exc_info=True)
            raise


def parse_args():
    """Parse command line arguments.

    Returns:
        Namespace with parsed arguments
    """
    parser = argparse.ArgumentParser(description="Touch Sensor Companion Device")
    parser.add_argument(
        "--data-dir",
        type=str,
        default=str(Path(__file__).parent.parent / "data"),
        help="Directory for storing data files",
    )
    parser.add_argument(
        "--led-device",
        type=str,
        default="/dev/spidev0.0",
        help="Device path for the LED strip",
    )
    parser.add_argument(
        "--led-count", type=int, default=30, help="Number of LEDs in the strip"
    )
    parser.add_argument(
        "--led-frequency", type=int, default=800, help="Frequency for the LED strip"
    )
    parser.add_argument(
        "--i2c-address",
        type=lambda x: int(x, 0),  # Allow hex input (0x5A)
        default=0x5A,
        help="I2C address for the MPR121 sensor (default: 0x5A)",
    )
    parser.add_argument("--i2c-bus", type=int, default=1, help="I2C bus number")
    parser.add_argument(
        "--host", type=str, default="0.0.0.0", help="Host to bind the web server to"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port for the web server"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Logging level",
    )

    return parser.parse_args()


def main():
    """Main entry point for the application."""
    args = parse_args()

    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Create and start the application
    app = TouchCompanionApp(
        data_dir=Path(args.data_dir),
        led_device=args.led_device,
        led_count=args.led_count,
        led_frequency=args.led_frequency,
        i2c_address=args.i2c_address,
        i2c_bus=args.i2c_bus,
        host=args.host,
        port=args.port,
    )

    try:
        app.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down")
        app.stop()
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}")
        app.stop()
        sys.exit(1)


if __name__ == "__main__":
    main()
