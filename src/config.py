"""
Configuration settings for Touch Companion Application

This module provides:
- Global application settings
- Environment-specific configurations
- Constants used throughout the application
"""

import os
from pathlib import Path

# Base application paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = DATA_DIR

# Database settings
DATABASE_PATH = DATA_DIR / "touch_data.db"
DATABASE_BACKUP_DIR = DATA_DIR / "backups"
DATABASE_RETENTION_DAYS = 30  # How long to keep detailed touch events

# Sensor settings
SENSOR_POLL_INTERVAL_MS = 10  # How often to poll the sensor (in milliseconds)
TOUCH_DEBOUNCE_MS = 50  # Minimum time between touch events (debounce)
MAX_SENSOR_ERROR_COUNT = 5  # Maximum consecutive errors before reinitializing
SENSOR_ERROR_COOLDOWN_SEC = 10  # Cooldown period after errors

# Emotional state settings
EMOTIONAL_STATE_SETTINGS = {
    "TOUCH_BUFFER_MAX_SIZE": 20,  # Maximum number of touch events to keep in buffer
    "TOUCH_BUFFER_MAX_AGE_SEC": 300,  # Maximum age of touch events in buffer (5 minutes)
    "SAD_TO_GLAD_THRESHOLD": 10,  # Min touches in buffer to transition to glad
    "GLAD_TO_SAD_THRESHOLD": 3,  # Max touches in buffer to transition to sad
    "TRANSITION_DURATION_SEC": 5.0,  # Duration of color transition animation
    "TRANSITION_STEPS": 50,  # Number of steps for smooth color transition
    "SAD_COLOR": (0, 0, 255),  # Blue for sad state (RGB)
    "GLAD_COLOR": (255, 255, 0),  # Yellow for glad state (RGB)
}

# Statistics engine settings
STATISTICS_SETTINGS = {
    "UPDATE_INTERVAL_SEC": 10,  # How often to update statistics
    "CACHE_TTL": {  # Time-to-live for cached statistics (in seconds)
        "all_time": 3600,  # 1 hour for all-time stats (changes slowly)
        "today": 300,  # 5 minutes for today's stats
        "hour": 60,  # 1 minute for hourly stats
        "minute": 10,  # 10 seconds for minute stats
    },
}

# Web application settings
WEB_SETTINGS = {
    "HOST": "0.0.0.0",  # Default host to bind to
    "PORT": 8000,  # Default port
    "CORS_ORIGINS": ["*"],  # CORS allowed origins
    "SSE_KEEP_ALIVE_SEC": 30,  # Server-sent events keep-alive interval
}

# LED strip settings
LED_SETTINGS = {
    "LED_COUNT": 16,  # Number of LEDs in the strip
    "LED_BRIGHTNESS": 100,  # Brightness (0-255)
    "LED_MAX_BRIGHTNESS": 150,  # Maximum brightness for high-intensity states
}

# Get environment-specific overrides
ENV = os.getenv("APP_ENV", "development").lower()

if ENV == "production":
    # Production overrides
    DEBUG = False
    WEB_SETTINGS["CORS_ORIGINS"] = ["http://localhost:8000"]
    LED_SETTINGS["LED_BRIGHTNESS"] = 80  # Lower brightness for production

elif ENV == "development":
    # Development overrides
    DEBUG = True
    WEB_SETTINGS["PORT"] = 8000

elif ENV == "test":
    # Test environment overrides
    DEBUG = True
    DATABASE_PATH = ":memory:"  # Use in-memory database for tests
    WEB_SETTINGS["PORT"] = 8080
