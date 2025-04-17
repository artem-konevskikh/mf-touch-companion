#!/usr/bin/env python3
"""
Touch Companion Web Server - Main Entry Point.

This module provides the entry point for starting the Touch Companion web server
that monitors touch sensors and controls LED strips based on interaction thresholds.
"""

import logging

from src.new_logic.config import AppConfig, parse_arguments
from src.new_logic.app import TouchCompanionApp


def setup_basic_logging(config: AppConfig) -> None:
    """Configure basic logging before full app setup.

    Args:
        config: Application configuration
    """
    log_format = "%(asctime)s - %(levelname)s - %(message)s"
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)

    # Reset root logger to avoid duplicate logs
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    # Configure only a console handler for simplicity
    logging.basicConfig(
        level=log_level,
        format=log_format,
    )


def main() -> None:
    """Main entry point for the application."""
    # Parse command line arguments
    config = parse_arguments()

    # Set up basic logging
    # setup_basic_logging(config)

    # Initialize and run application
    app = TouchCompanionApp(config)
    app.run()


if __name__ == "__main__":
    main()
