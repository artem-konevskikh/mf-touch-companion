# Touch Companion

An interactive touch-sensitive companion device for Raspberry Pi that responds to touch interactions by changing its emotional state.

## Features

- Real-time touch detection via MPR121 capacitive touch sensor
- Emotional state engine that transitions between "sad" and "glad" states based on touch frequency
- LED visualization of emotional states with smooth transitions
- Dual-display interface showing statistics in Russian language
- Asynchronous web server with real-time updates
- SQLite database for persistent storage of touch events
- Comprehensive statistics with Russian number formatting

## Hardware Requirements

- Raspberry Pi 5
- MPR121 capacitive touch sensor
- RGB LED strip (compatible with pi5neo library)
- Two display monitors connected to the HDMI ports
- Touch-sensitive surfaces connected to MPR121

## Software Prerequisites

- Raspberry Pi OS (Bookworm or newer)
- Python 3.9 or newer
- I2C enabled for MPR121 communication

### Enabling I2C on Raspberry Pi 5

1. Open Raspberry Pi Configuration:
   ```bash
   sudo raspi-config
   ```

2. Navigate to "Interface Options" > "I2C" and enable it

3. Reboot your Raspberry Pi:
   ```bash
   sudo reboot
   ```

4. Verify I2C is enabled:
   ```bash
   ls /dev/i2c*
   # Should show at least /dev/i2c-1
   ```

### Display Configuration for Raspberry Pi 5

The Raspberry Pi 5 has two micro-HDMI ports that can drive dual displays:
- HDMI0: Primary display
- HDMI1: Secondary display

1. Make sure both displays are connected before powering on the Pi

2. Check if both displays are detected:
   ```bash
   tvservice -l
   ```

3. For the systemd services, the display identifiers are usually:
   - Primary display: `DISPLAY=:0`
   - Secondary display: `DISPLAY=:0.1`

## Installation

1. Clone this repository:

```bash
git clone https://github.com/yourusername/touch-companion.git
cd touch-companion
```

2. Create a Python virtual environment and install dependencies:

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
deactivate
```

3. Create necessary directories:

```bash
mkdir -p data
mkdir -p frontend/static/css
mkdir -p frontend/static/js
mkdir -p frontend/static/img
mkdir -p frontend/templates
```

4. Connect your hardware according to the following pinout:

- MPR121 sensor: Connect to I2C pins (SDA, SCL)
- LED strip: Connect using the Pi5Neo library configuration
- Connect your displays to the Raspberry Pi

The provided hardware interface implementations are already configured to work with your specific hardware using the smbus2 and pi5neo libraries.

## Configuration

You can customize application behavior by editing `config.py`. The most important settings include:

- `EMOTIONAL_STATE_SETTINGS`: Configure thresholds for state transitions
- `LED_SETTINGS`: Configure LED strip parameters
- `DATABASE_RETENTION_DAYS`: Set how long to keep touch data

## Running the Application

To start the application manually:

```bash
source .venv/bin/activate
python main.py
deactivate
```

Optional command-line arguments:

```bash
python main.py --host 0.0.0.0 --port 8000 --log-level info --dev
```

- `--host`: Host to bind the server to (default: 0.0.0.0)
- `--port`: Port to bind the server to (default: 8000)
- `--log-level`: Logging level (default: info)
- `--dev`: Enable development mode with auto-reload

Once running, you can access the interfaces in your browsers:
- Main display: `http://localhost:8000/`
- Statistics display: `http://localhost:8000/statistics`

## Installation as a Service

To run the application automatically at system startup:

1. Copy the systemd service files to the systemd directory:

```bash
sudo cp touch-companion.service /etc/systemd/system/
sudo cp touch-companion-display1.service /etc/systemd/system/
sudo cp touch-companion-display2.service /etc/systemd/system/
```

2. Enable and start the services:

```bash
sudo systemctl daemon-reload
sudo systemctl enable touch-companion.service
sudo systemctl enable touch-companion-display1.service
sudo systemctl enable touch-companion-display2.service
sudo systemctl start touch-companion.service
# The display services will start automatically after 60 seconds
```

3. Check the services status:

```bash
sudo systemctl status touch-companion.service
sudo systemctl status touch-companion-display1.service
sudo systemctl status touch-companion-display2.service
```

4. View logs with:

```bash
sudo journalctl -u touch-companion.service -f
sudo journalctl -u touch-companion-display1.service -f
sudo journalctl -u touch-companion-display2.service -f
```

### Display Configuration

The browser services are configured to:
- Open the main page on Display 1 (`:0`)
- Open the statistics page on Display 2 (`:0.1`)

#### Raspberry Pi 5 Display Configuration

For Raspberry Pi 5 with dual displays:

1. No special configuration is needed in `/boot/config.txt` as the Pi 5 natively supports dual displays.

2. Make sure both micro-HDMI ports are connected:
   - HDMI0 is the port closest to the USB-C power connector
   - HDMI1 is the second micro-HDMI port

3. If using different display identifiers, you may need to modify the service files:
   ```bash
   # Check which displays are available
   echo $DISPLAY
   # Edit service files if needed
   sudo nano /etc/systemd/system/touch-companion-display1.service
   sudo nano /etc/systemd/system/touch-companion-display2.service
   ```

4. Reload service files after any changes:
   ```bash
   sudo systemctl daemon-reload
   ```

#### Manual Display Testing

To manually test your display configuration before enabling services:

```bash
# For Display 1
DISPLAY=:0 chromium-browser --kiosk http://localhost:8000/

# For Display 2
DISPLAY=:0.1 chromium-browser --kiosk http://localhost:8000/statistics
```

## API Documentation

The application provides a REST API for interacting with the device:

- Touch data: `/api/touch/*`
- Statistics: `/api/statistics/*`
- Emotional state: `/api/emotional-state/*`

API documentation is available at `http://localhost:8000/docs`

## Custom Hardware Interfaces

You'll need to implement the following custom hardware interfaces:

### MPR121 Touch Sensor Interface

Create a class in `hardware/mpr121_interface.py` that provides at minimum:

```python
class MPR121Sensor:
    def initialize(self):
        # Initialize the sensor
        pass
        
    def read_touch_state(self):
        # Read current touch state and return a bitmask
        # Bit 0 for sensor 0, bit 1 for sensor 1, etc.
        return 0  # Replace with actual implementation
```

### LED Strip Interface

Create a class in `hardware/led_strip_interface.py` that provides at minimum:

```python
class LEDStrip:
    def initialize(self):
        # Initialize the LED strip
        pass
        
    def set_color(self, r, g, b):
        # Set all LEDs to the specified RGB color
        pass
```

## Installation as a Service

To run the application automatically at system startup:

1. Create a Python virtual environment and install dependencies (if not already done):

```bash
cd /home/pi/touch-companion
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
deactivate
```

2. Copy the systemd service files to the systemd directory:

```bash
sudo cp touch-companion.service /etc/systemd/system/
sudo cp touch-companion-display1.service /etc/systemd/system/
sudo cp touch-companion-display2.service /etc/systemd/system/
```

3. Enable and start the services:

```bash
sudo systemctl enable touch-companion.service
sudo systemctl enable touch-companion-display1.service
sudo systemctl enable touch-companion-display2.service
sudo systemctl start touch-companion.service
# The display services will start automatically after 60 seconds
```

4. Check the services status:

```bash
sudo systemctl status touch-companion.service
sudo systemctl status touch-companion-display1.service
sudo systemctl status touch-companion-display2.service
```

5. View logs with:

```bash
sudo journalctl -u touch-companion.service -f
sudo journalctl -u touch-companion-display1.service -f
sudo journalctl -u touch-companion-display2.service -f
```

### Display Configuration

The services are configured to use:
- Display 1 (`:0`): Shows the main page
- Display 2 (`:0.1`): Shows the statistics page

To configure multiple displays on Raspberry Pi:

1. Edit your `/boot/config.txt` file to enable the second display
2. Configure Xorg to use both displays (this may vary based on your display setup)
3. You may need to adjust the `DISPLAY` environment variable in the service files based on your specific multi-display configuration

## Troubleshooting

### Common Issues on Raspberry Pi 5

- **I2C Not Working**
  - Check if I2C is enabled: `ls /dev/i2c*`
  - Check connected devices: `i2cdetect -y 1`
  - Verify wiring connections to the sensor

- **Pi5Neo Device Not Found**
  - Check if the device is available: `ls /dev/pi5neo*`
  - You may need to install or configure the pi5neo driver
  - Verify LED strip power and signal connections

- **Display Issues**
  - Verify both displays are detected: `tvservice -l`
  - Test displays manually as described above
  - Check HDMI cables are properly connected to the correct ports

- **Browser Not Starting**
  - Check if X server is running: `echo $DISPLAY`
  - Verify Chromium is installed: `which chromium`
  - Check logs: `sudo journalctl -u touch-companion-display1.service`

- **Performance Issues**
  - Check CPU temperature: `vcgencmd measure_temp`
  - Monitor CPU usage: `top`
  - Ensure you're using adequate power supply

### Application Logs

- Check application logs in `data/application.log`
- Check service logs: `sudo journalctl -u touch-companion.service -f`
- Monitor database operations: `data/database.log`

### Service Management

```bash
# Restart the application
sudo systemctl restart touch-companion.service

# Restart display browsers
sudo systemctl restart touch-companion-display1.service
sudo systemctl restart touch-companion-display2.service

# Check service status
sudo systemctl status touch-companion.service
```

## License

MIT License