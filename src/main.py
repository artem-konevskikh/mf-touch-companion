#!/usr/bin/env python3
"""Touch Companion Application
Main entry point for the Raspberry Pi touch-sensitive companion device

This script:
- Sets up the necessary configurations
- Handles command-line arguments
- Initializes all application modules
- Starts the FastAPI web server
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys
from typing import NoReturn

import uvicorn

# Import application components
from src.api.app import app  # noqa: F401 - Used by uvicorn config
from src.modules.database import db

# Ensure project directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("data/application.log"), logging.StreamHandler()],
)
logger = logging.getLogger("main")


def signal_handler(sig: int, frame: object) -> NoReturn:
    """Handle termination signals for graceful shutdown."""
    logger.info(f"Received signal {sig}, shutting down...")
    # Stop asyncio event loop - This will trigger the shutdown events in FastAPI
    asyncio.get_event_loop().stop()
    sys.exit(0)


async def database_maintenance() -> None:
    """Periodic database maintenance task."""
    while True:
        try:
            # Clean old data
            deleted_records = await db.clean_old_data()
            if deleted_records > 0:
                logger.info(f"Database maintenance: Deleted {deleted_records} old records")

            # Optimize database
            await db.optimize_database()
            logger.info("Database maintenance: Optimization completed")

        except Exception as e:
            logger.error(f"Error in database maintenance: {str(e)}")

        # Run maintenance daily
        await asyncio.sleep(24 * 60 * 60)  # 24 hours


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Touch Companion Application")

    parser.add_argument("--host", default="0.0.0.0", help="Host to bind the server to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind the server to")
    parser.add_argument(
        "--log-level",
        default="info",
        choices=["debug", "info", "warning", "error", "critical"],
        help="Log level",
    )
    parser.add_argument("--dev", action="store_true", help="Development mode")

    return parser.parse_args()


async def start_server(config: uvicorn.Config) -> None:
    """Start the uvicorn server with the given configuration."""
    server = uvicorn.Server(config)
    await server.serve()


async def main() -> None:
    """Main entry point for the application."""
    # Parse arguments
    args = parse_arguments()

    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Set log level
    log_level = getattr(logging, args.log_level.upper())
    logging.getLogger().setLevel(log_level)

    # Configure uvicorn server
    config = uvicorn.Config(
        "src.api.app:app",
        host=args.host,
        port=args.port,
        log_level=args.log_level.lower(),
        reload=args.dev,
        reload_includes=["*.py"],
        reload_excludes=["*.pyc"],
        loop="asyncio",
        access_log=True,
    )

    # Create event loop
    loop = asyncio.get_event_loop()

    # Start database maintenance task
    loop.create_task(database_maintenance())

    # Log server startup
    logger.info(f"Starting Touch Companion server on {args.host}:{args.port}")
    if args.dev:
        logger.info("Development mode enabled (auto-reload)")

    # Start the server
    await start_server(config)


if __name__ == "__main__":
    asyncio.run(main())
