#!/usr/bin/env python3
"""
Touch Companion Application
Main entry point for the Raspberry Pi touch-sensitive companion device

This script:
- Sets up the necessary configurations
- Handles command-line arguments
- Initializes all application modules
- Starts the FastAPI web server
"""

import os
import sys
import asyncio
import argparse
import logging
import uvicorn
from pathlib import Path
import signal

# Ensure project directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("data/application.log"), logging.StreamHandler()],
)
logger = logging.getLogger("main")

# Import application components
from api.app import app
from modules.database import db
from modules.emotional_state import EmotionalStateEngine
from modules.sensor import TouchSensorManager
from modules.statistics import StatisticsEngine
from api.app import emotional_state_engine, touch_sensor_manager, statistics_engine


# Create required directories
def create_directories():
    """Create necessary directories if they don't exist."""
    Path("data").mkdir(exist_ok=True)
    Path("frontend/static/css").mkdir(parents=True, exist_ok=True)
    Path("frontend/static/js").mkdir(parents=True, exist_ok=True)
    Path("frontend/static/img").mkdir(parents=True, exist_ok=True)
    Path("frontend/templates").mkdir(parents=True, exist_ok=True)


# Database maintenance task
async def database_maintenance():
    """Periodic database maintenance task."""
    while True:
        try:
            # Clean old data
            deleted_records = await db.clean_old_data()
            if deleted_records > 0:
                logger.info(
                    f"Database maintenance: Deleted {deleted_records} old records"
                )

            # Optimize database
            await db.optimize_database()
            logger.info("Database maintenance: Optimization completed")

        except Exception as e:
            logger.error(f"Error in database maintenance: {str(e)}")

        # Run maintenance daily
        await asyncio.sleep(24 * 60 * 60)  # 24 hours


# Signal handler for graceful shutdown
def signal_handler(sig, frame):
    """Handle termination signals for graceful shutdown."""
    logger.info(f"Received signal {sig}, shutting down...")
    # Stop asyncio event loop - This will trigger the shutdown events in FastAPI
    asyncio.get_event_loop().stop()
    sys.exit(0)


# Parse command-line arguments
def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Touch Companion Application")

    parser.add_argument("--host", default="0.0.0.0", help="Host to bind the server to")
    parser.add_argument(
        "--port", type=int, default=8000, help="Port to bind the server to"
    )
    parser.add_argument(
        "--log-level",
        default="info",
        choices=["debug", "info", "warning", "error", "critical"],
        help="Log level",
    )
    parser.add_argument("--dev", action="store_true", help="Development mode")

    return parser.parse_args()


# Main function
def main():
    """Main entry point for the application."""
    # Parse arguments
    args = parse_arguments()

    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create required directories
    create_directories()

    # Set log level
    log_level = getattr(logging, args.log_level.upper())
    logging.getLogger().setLevel(log_level)

    # Start database maintenance task
    loop = asyncio.get_event_loop()
    loop.create_task(database_maintenance())

    # Start the FastAPI server
    logger.info(f"Starting Touch Companion server on {args.host}:{args.port}")

    # Determine reload setting based on dev mode
    reload = args.dev
    if reload:
        logger.info("Development mode enabled (auto-reload)")

    # Start the server using uvicorn
    uvicorn.run(
        "api.app:app",
        host=args.host,
        port=args.port,
        log_level=args.log_level.lower(),
        reload=reload,
    )


if __name__ == "__main__":
    main()
