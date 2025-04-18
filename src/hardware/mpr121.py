import time
import smbus2 as smbus


class MPR121TouchSensor:
    # MPR121 Register Map
    TOUCH_STATUS_REG = 0x00  # Touch status register
    ELECTRODE_CONFIG_REG = 0x5E  # Electrode configuration register
    FILTER_CONFIG_REG = 0x5D  # Filter configuration register

    # Other important registers
    TOUCH_THRESHOLD_REG = 0x41  # Touch threshold register (first electrode)
    RELEASE_THRESHOLD_REG = 0x42  # Release threshold register (first electrode)

    def __init__(self, i2c_address=0x5A, i2c_bus=1):
        """Initialize the MPR121 touch sensor.

        Args:
            i2c_address: The I2C address of the MPR121 (default: 0x5A)
            i2c_bus: The I2C bus number (default: 1 for Raspberry Pi)
        """
        self.i2c_address = i2c_address
        self.bus = smbus.SMBus(i2c_bus)

        # Touch tracking variables
        self.touch_count = [0] * 12  # Count for each electrode
        self.touch_start_times = [0.] * 12  # Start time for each touch
        self.touch_durations = [
            [] for _ in range(12)
        ]  # List of durations for each electrode
        self.current_touches = [False] * 12  # Current touch status

        # Initialize the sensor
        self._initialize_sensor()

    def _initialize_sensor(self):
        """Initialize the MPR121 sensor with default settings."""
        # Reset the device
        self.bus.write_byte_data(self.i2c_address, self.ELECTRODE_CONFIG_REG, 0x00)

        # Configure touch and release thresholds for all electrodes
        for i in range(12):
            self.bus.write_byte_data(
                self.i2c_address, self.TOUCH_THRESHOLD_REG + 2 * i, 12*2
            )  # Touch threshold
            self.bus.write_byte_data(
                self.i2c_address, self.RELEASE_THRESHOLD_REG + 2 * i, 6*2
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
        self.bus.write_byte_data(self.i2c_address, 0x5C, 0x10)  # Auto-config control

        # Enable all 12 electrodes and set to run mode
        self.bus.write_byte_data(
            self.i2c_address, self.ELECTRODE_CONFIG_REG, 0x8F
        )  # Enable electrodes

    def read_touch_status(self):
        """Read the current touch status from the MPR121.

        Returns:
            A 12-element list of boolean values indicating touch status for each electrode.
        """
        # Read the touch status registers (2 bytes)
        touch_status = self.bus.read_i2c_block_data(
            self.i2c_address, self.TOUCH_STATUS_REG, 2
        )

        # Convert to a 16-bit value (though only the first 12 bits are used)
        touch_value = touch_status[0] | (touch_status[1] << 8)

        # Extract individual electrode statuses (1 = touched, 0 = not touched)
        touch_status_list = [(touch_value >> i) & 1 == 1 for i in range(12)]

        return touch_status_list

    def update(self):
        """Update touch status and track touches and durations."""
        current_status = self.read_touch_status()
        current_time = time.time()

        for i in range(12):
            # If electrode was not touched and now is touched (touch start)
            if not self.current_touches[i] and current_status[i]:
                self.current_touches[i] = True
                self.touch_count[i] += 1
                self.touch_start_times[i] = current_time

            # If electrode was touched and now is not touched (touch end)
            elif self.current_touches[i] and not current_status[i]:
                self.current_touches[i] = False
                duration = current_time - self.touch_start_times[i]
                self.touch_durations[i].append(duration)

        # Update the current touch status
        self.current_touches = current_status

    def get_touch_count(self, electrode=None):
        """Get the number of touches for a specific electrode or all electrodes.

        Args:
            electrode: The electrode index (0-11) or None for all electrodes.

        Returns:
            The touch count for the specified electrode or a list of counts.
        """
        if electrode is not None:
            return self.touch_count[electrode]
        return self.touch_count

    def get_touch_durations(self, electrode=None):
        """Get the durations of touches for a specific electrode or all electrodes.

        Args:
            electrode: The electrode index (0-11) or None for all electrodes.

        Returns:
            A list of touch durations for the specified electrode or a list of lists.
        """
        if electrode is not None:
            return self.touch_durations[electrode]
        return self.touch_durations

    def get_average_touch_duration(self, electrode=None):
        """Get the average touch duration for a specific electrode or all electrodes.

        Args:
            electrode: The electrode index (0-11) or None for all electrodes.

        Returns:
            The average touch duration or a list of average durations.
        """
        if electrode is not None:
            durations = self.touch_durations[electrode]
            return sum(durations) / len(durations) if durations else 0

        avg_durations = []
        for durations in self.touch_durations:
            avg_durations.append(sum(durations) / len(durations) if durations else 0)
        return avg_durations

    def reset_statistics(self, electrode=None):
        """Reset touch statistics for a specific electrode or all electrodes.

        Args:
            electrode: The electrode index (0-11) or None for all electrodes.
        """
        if electrode is not None:
            self.touch_count[electrode] = 0
            self.touch_durations[electrode] = []
            return

        self.touch_count = [0] * 12
        self.touch_durations = [[] for _ in range(12)]
