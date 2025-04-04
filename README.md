# Touch Sensor Companion Device

An interactive touch-sensitive companion device for Raspberry Pi 5 that responds to touch interactions with emotional states and provides a web-based statistics dashboard.

## Features

- Touch event detection and tracking using MPR121 capacitive touch sensor
- Emotional state engine that transitions between "sad" and "glad" states based on touch frequency
- LED feedback with color changes and effects based on emotional state
- Russian-language web dashboard showing touch statistics
- Real-time updates via server-sent events
- Automatic startup via systemd services

## Hardware Requirements

- Raspberry Pi 5
- MPR121 capacitive touch sensor
- RGB LED strip (compatible with pi5neo library)
- Display for web interface

## Software Requirements

- Python 3.9+
- SQLite
- FastAPI
- smbus2 ≥ 0.5.0
- pi5neo ≥ 1.0.5
- uvicorn

## Directory Structure

```
touch-companion/
├── services/                  # Systemd service files
│   ├── touch-companion.service
│   └── touch-companion-browser.service
├── src/                       # Source code
│   ├── __init__.py
│   ├── main.py                # Main application entry point
│   ├── database.py            # Database module
│   ├── touch_sensor.py        # Core sensor module 
│   ├── emotional_state_engine.py # Emotional state engine
│   ├── led_strip.py           # LED strip controller
│   ├── webapp.py              # FastAPI web application
│   ├── static/                # Static files for web interface
│   └── templates/             # HTML templates
│       └── index.html         # Main dashboard template
└── README.md                  # This file
```

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-username/touch-companion.git
cd touch-companion
```

### 2. Install required packages

```bash
# Update package list
sudo apt update

# Install required system packages
sudo apt install -y python3-pip python3-dev i2c-tools

# Install required Python packages
pip3 install fastapi uvicorn smbus2>=0.5.0 pi5neo>=1.0.5 pydantic typing_extensions
```

### 3. Enable I2C interface

```bash
# Enable I2C interface if not already enabled
sudo raspi-config
# Navigate to: Interfacing Options > I2C > Yes
```

### 4. Install systemd services

```bash
# Copy service files to systemd directory
sudo cp services/touch-companion.service /etc/systemd/system/
sudo cp services/touch-companion-browser.service /etc/systemd/system/

# Reload systemd configuration
sudo systemctl daemon-reload

# Enable services to start at boot
sudo systemctl enable touch-companion.service
sudo systemctl enable touch-companion-browser.service
```

### 5. Configure hardware

Connect the MPR121 touch sensor to the Raspberry Pi's I2C pins:
- VCC to 3.3V
- GND to Ground
- SCL to SCL (GPIO 3)
- SDA to SDA (GPIO 2)

Connect the RGB LED strip:
- Follow the pi5neo library guidelines for connecting your specific LED strip

### 6. Start the services

```bash
# Start the main service
sudo systemctl start touch-companion.service

# The browser service will start automatically after 1 minute
```

## Usage

### Accessing the Dashboard

The web dashboard will automatically open in full-screen mode on the connected display. Alternatively, you can access it from any device on the same network by navigating to:

```
http://<raspberry-pi-ip>:8000
```

### Statistics Shown

The dashboard displays the following statistics in Russian:
- Total all-time touch count
- Last hour touch count
- Today's touch count (since midnight)
- Average touch duration
- Time spent in each emotional state today
- Current emotional state (represented by an emoji)

### Emotional States

The device has two emotional states:
- **Sad (грустный)** - Represented by blue color and (︶︹︶) emoji
- **Glad (рад)** - Represented by yellow/gold color and (◠‿◠) emoji

The state changes based on touch frequency:
- Transitions from sad to glad when touch frequency exceeds 5 touches per minute
- Transitions from glad to sad when touch frequency drops below 2 touches per minute

### Custom Configuration

You can customize various parameters by editing the source code or passing command-line arguments:

```bash
python3 -m src.main --help
```

Available parameters include:
- `--data-dir`: Directory for storing data files
- `--led-device`: Device path for the LED strip
- `--led-count`: Number of LEDs in the strip
- `--led-frequency`: Frequency for the LED strip
- `--i2c-address`: I2C address for the MPR121 sensor
- `--i2c-bus`: I2C bus number
- `--host`: Host to bind the web server to
- `--port`: Port for the web server
- `--log-level`: Logging level

## Troubleshooting

### Service Issues

Check the service status:

```bash
# Check main service status
sudo systemctl status touch-companion.service

# Check browser service status
sudo systemctl status touch-companion-browser.service
```

View logs:

```bash
# View main service logs
sudo journalctl -u touch-companion.service

# View browser service logs
sudo journalctl -u touch-companion-browser.service
```

### I2C Issues

Check if the MPR121 sensor is detected:

```bash
sudo i2cdetect -y 1
```

The sensor should appear at address 0x5A.

### LED Issues

Ensure the pi5neo device is properly configured:

```bash
ls -la /dev/pi5neo*
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.