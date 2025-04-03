"""
MPR121 Touch Sensor Interface for Touch Companion Application

This module provides an interface to the MPR121 capacitive touch sensor
using the provided custom implementation.
"""

import time
import logging
import smbus2 as smbus

logger = logging.getLogger("hardware.mpr121")


class MPR121Sensor:
    """Interface with the MPR121 capacitive touch sensor."""

    # MPR121 Register Map
    TOUCH_STATUS_REG = 0x00  # Touch status register
    ELECTRODE_CONFIG_REG = 0x5E  # Electrode configuration register
    FILTER_CONFIG_REG = 0x5D  # Filter configuration register

    # Other important registers
    TOUCH_THRESHOLD_REG = 0x41  # Touch threshold register (first electrode)
    RELEASE_THRESHOLD_REG = 0x42  # Release threshold register (first electrode)

    def __init__(
        self, i2c_address=0x5A, i2c_bus=1, touch_threshold=12, release_threshold=6
    ):
        """
        Initialize the MPR121 sensor interface.

        Args:
            i2c_address: I2C address of the MPR121 sensor
            i2c_bus: I2C bus number
            touch_threshold: Threshold for detecting touches
            release_threshold: Threshold for detecting releases
        """
        self.i2c_address = i2c_address
        self.bus = None
        self.touch_threshold = touch_threshold
        self.release_threshold = release_threshold
        self.initialized = False

        # Touch tracking variables
        self.current_touches = [False] * 12  # Current touch status
        self.touch_start_times = [0] * 12  # Start time for each touch

    def initialize(self):
        """Initialize the MPR121 sensor."""
        try:
            # Open the I2C bus
            self.bus = smbus.SMBus(1)  # 1 is the default for Raspberry Pi

            # Reset the device
            self.bus.write_byte_data(self.i2c_address, self.ELECTRODE_CONFIG_REG, 0x00)

            # Configure touch and release thresholds for all electrodes
            for i in range(12):
                self.bus.write_byte_data(
                    self.i2c_address,
                    self.TOUCH_THRESHOLD_REG + 2 * i,
                    self.touch_threshold,
                )  # Touch threshold
                self.bus.write_byte_data(
                    self.i2c_address,
                    self.RELEASE_THRESHOLD_REG + 2 * i,
                    self.release_threshold,
                )  # Release threshold

            # Configure the sensor with default settings
            # These are typical values from Adafruit/Sparkfun libraries
            self.bus.write_byte_data(self.i2c_address, 0x2B, 0x01)  # MHD Rising
            self.bus.write_byte_data(self.i2c_address, 0x2C, 0x01)  # NHD Rising
            self.bus.write_byte_data(self.i2c_address, 0x2D, 0x00)  # NCL Rising
            self.bus.write_byte_data(self.i2c_address, 0x2E, 0x00)  # FDL Rising

            self.bus.write_byte_data(self.i2c_address, 0x2F, 0x01)  # MHD Falling
            self.bus.write_byte_data(self.i2c_address, 0x30, 0x01)  # NHD Falling
            self.bus.write_byte_data(self.i2c_address, 0x31, 0xFF)  # NCL Falling
            self.bus.write_byte_data(self.i2c_address, 0x32, 0x02)  # FDL Falling

            # Configure electrode charge/discharge current and timing
            self.bus.write_byte_data(
                self.i2c_address, 0x5C, 0x10
            )  # Auto-config control

            # Enable all 12 electrodes and set to run mode
            self.bus.write_byte_data(
                self.i2c_address, self.ELECTRODE_CONFIG_REG, 0x8F
            )  # Enable electrodes

            self.initialized = True
            logger.info("MPR121 sensor initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize MPR121 sensor: {str(e)}")
            self.initialized = False

        return self.initialized

    def read_touch_state(self):
        """
        Read the current touch state from the sensor.

        Returns:
            Bitmask of touch states (bit 0 for sensor 0, bit 1 for sensor 1, etc.)
        """
        if not self.initialized or not self.bus:
            logger.warning("Attempting to read from uninitialized MPR121 sensor")
            return 0

        try:
            # Read the touch status registers (2 bytes)
            touch_status = self.bus.read_i2c_block_data(
                self.i2c_address, self.TOUCH_STATUS_REG, 2
            )

            # Convert to a 16-bit value (though only the first 12 bits are used)
            touch_value = touch_status[0] | (touch_status[1] << 8)

            # Update current touch status and record touch start times
            current_time = time.time()
            for i in range(12):
                is_touched = (touch_value >> i) & 1 == 1

                # If electrode was not touched and now is touched (touch start)
                if not self.current_touches[i] and is_touched:
                    self.touch_start_times[i] = current_time

                self.current_touches[i] = is_touched

            return touch_value

        except Exception as e:
            logger.error(f"Error reading from MPR121 sensor: {str(e)}")
            return 0

    def get_touch_duration(self, sensor_id):
        """
        Get the current duration of a touch in milliseconds.

        Args:
            sensor_id: ID of the sensor (0-11)

        Returns:
            Duration in milliseconds or 0 if not touched
        """
        if sensor_id < 0 or sensor_id >= 12:
            return 0

        if self.current_touches[sensor_id]:
            duration = time.time() - self.touch_start_times[sensor_id]
            return int(duration * 1000)  # Convert to milliseconds

        return 0
