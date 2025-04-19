#!/usr/bin/env python3
"""
Configuration module for Touch Companion application.

Provides Pydantic models for application configuration and command-line parsing.
"""

import argparse
from typing import Optional

from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    """Application configuration parameters using Pydantic for validation."""

    # MPR121 Sensor Config
    i2c_address: int = Field(
        default=0x5A, description="I2C address of the MPR121 sensor"
    )
    i2c_bus: int = Field(default=1, description="I2C bus number")
    history_duration_sec: int = Field(
        default=3600, description="Duration in seconds to keep touch history"
    )

    # LED Strip Config
    led_device: str = Field(
        default="/dev/spidev0.0", description="SPI device path for LED strip"
    )
    num_leds: int = Field(default=280, description="Number of LEDs in the strip")
    led_frequency: int = Field(default=800, description="LED strip frequency (Hz)")

    # State Logic Config
    touch_threshold: int = Field(
        default=20, description="Touches in the last hour to trigger GLAD state"
    )
    update_interval_sec: float = Field(
        default=0.1, description="Interval in seconds between sensor checks"
    )

    # Color and Animation Config
    sad_color: tuple[int, int, int] = Field(
        default=(0, 0, 255), description="RGB color for SAD state (Blue)"
    )
    glad_color: tuple[int, int, int] = Field(
        default=(255, 0, 0), description="RGB color for GLAD state (Red)"
    )
    transition_steps: int = Field(
        default=50, description="Number of steps for color transitions"
    )

    # Server Config
    host: str = Field(default="0.0.0.0", description="Host interface to bind server to")
    port: int = Field(default=8000, description="Port to run server on")

    # Logging Config
    log_level: str = Field(default="info", description="Logging level")
    log_file: Optional[str] = Field(default=None, description="Path to log file")

    # Camera and API Config
    camera_enabled: bool = Field(
        default=True, description="Enable camera functionality"
    )
    cam_interval: int = Field(
        default=5, description="Minimum interval between camera captures in seconds"
    )
    ya_api_url: str = Field(
        default="https://art.ycloud.eazify.net:8443/comp",
        description="API endpoint URL for image processing",
    )
    response_display_time: int = Field(
        default=120, description="Time to display API responses in seconds"
    )


def parse_arguments() -> AppConfig:
    """Parse command line arguments and create application configuration.

    Only exposes the most commonly adjusted settings as command-line arguments,
    while using Pydantic defaults for the rest.

    Returns:
        AppConfig: Application configuration based on command line arguments
    """
    parser = argparse.ArgumentParser(
        description="Touch Companion Web Server",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Touch Sensor Config
    parser.add_argument(
        "--history-duration",
        type=int,
        help="Duration in seconds to keep touch history (default: 1 hour)",
    )

    # LED Strip Config
    parser.add_argument("--num-leds", type=int, help="Number of LEDs in the strip")

    # State Logic Config
    parser.add_argument(
        "--touch-threshold",
        type=int,
        help="Touches in the last hour to trigger GLAD state",
    )
    parser.add_argument(
        "--update-interval",
        type=float,
        help="Interval in seconds between sensor checks",
    )

    # Logging Config
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["debug", "info", "warning", "error", "critical"],
        help="Logging level",
    )

    args = parser.parse_args()

    # Prepare a config dict with only specified arguments (ignoring None values)
    config_dict = {}

    if args.history_duration is not None:
        config_dict["history_duration_sec"] = args.history_duration

    if args.num_leds is not None:
        config_dict["num_leds"] = args.num_leds

    if args.touch_threshold is not None:
        config_dict["touch_threshold"] = args.touch_threshold

    if args.update_interval is not None:
        config_dict["update_interval_sec"] = args.update_interval

    if args.log_level is not None:
        config_dict["log_level"] = args.log_level

    # Create and validate config with Pydantic (using defaults for unspecified values)
    return AppConfig(**config_dict)
