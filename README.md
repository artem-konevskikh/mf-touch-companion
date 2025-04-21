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
sudo apt update && sudo apt upgrade

# Install required system packages
sudo apt install -y python3-pip python3-dev i2c-tools
sudo apt install libcap-dev libatlas-base-dev ffmpeg libopenjp2-7
sudo apt install libkms++-dev libfmt-dev libdrm-dev
sudo apt install libcamera-dev
sudo apt install -y python3-libcamera python3-kms++ python3-picamzero

pip install --upgrade pip
pip install wheel
pip install rpi-libcamera rpi-kms picamera2
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

# Reload systemd configuration
sudo systemctl daemon-reload

# Enable services to start at boot
sudo systemctl enable touch-companion.service
```

### 5. Adding Desktop Icons

```bash
chmod 755 services/*.desktop
cp services/*.desktop ~/Desktop
```

### 6. Configure hardware

1. create `~/.config/wayfire.ini`:
```
[output:HDMI-A-2]
mode = 1440x600
```

2. add to `/boot/firmware/cmdline.txt`:

```
spidev.bufsiz=32768 video=HDMI-A-2:440x1920M@60,rotate=90,reflect_x 
```
spidev for long led strips, video for long screen

3. add to `/boot/firmware/config.txt` to configure screens:

```
disable_overscan=1
max_usb_current=1
hdmi_force_hotplug=1

# Screen 0 settings (HDMI0)
#hdmi_force_hotplug:0=1
config_hdmi_boost:0=10
hdmi_group:0=2
hdmi_mode:0=87
hdmi_cvt:0=1280 720 60 6 0 0 0

# Screen 1 settings (HDMI1)
hdmi_force_hotplug:1=1
config_hdmi_boost:1=10
hdmi_group:1=2
hdmi_mode:1=87
hdmi_cvt:1=144 1920 60
display_rotate:1=3  # 1=90 degrees, 2=180 degrees, 3=270 degrees
```

### 7. Start the services

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

The state changes based on touch count in the last hour:
- Transitions from sad to glad when there are 20 or more touches in the last hour
- Transitions from glad to sad when there are less than 20 touches in the last hour

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
```

View logs:

```bash
# View main service logs
sudo journalctl -u touch-companion.service
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