#!/usr/bin/env python3
"""
Camera Manager Module - Simplified.

Handles camera capture and API interactions with minimal complexity.
"""

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional
import tempfile
import json
import random
from pathlib import Path

import aiohttp
from picamzero import Camera

# Configure logger
logger = logging.getLogger("touch_companion.camera_manager")


class CameraManager:
    """Simplified manager for camera operations and API interactions."""

    def __init__(
        self,
        api_url: str,
        min_interval_sec: int = 5,
        response_display_time: int = 120,
    ):
        """Initialize the camera manager.

        Args:
            api_url: API endpoint URL
            min_interval_sec: Minimum seconds between captures
            response_display_time: Time in seconds to display API responses
        """
        self.api_url = api_url
        self.min_interval_sec = min_interval_sec
        self.response_display_time = response_display_time
        self.last_capture_time: float = 0.0
        self.latest_response: Optional[Dict[str, Any]] = None
        self._response_callback: Optional[
            Callable[[Dict[str, Any]], Awaitable[None]]
        ] = None
        self.compliments: List[str] = []
        self._load_compliments()
        self.camera: Optional[Camera] = None
        try:
            self.camera = Camera()
            logger.info("Camera initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize camera: {e}", exc_info=True)
            self.camera = None

    def _load_compliments(self):
        """Load compliments from the JSON file."""
        try:
            compliments_path = Path(__file__).parent / "compliments.json"
            if compliments_path.exists():
                with open(compliments_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.compliments = data.get("compliments", [])
                    if self.compliments:
                        logger.info(f"Loaded {len(self.compliments)} compliments.")
                    else:
                        logger.warning(
                            "Compliments file loaded but no compliments found."
                        )
            else:
                logger.warning(f"Compliments file not found at {compliments_path}")
        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Error loading compliments: {e}", exc_info=True)

    def register_response_callback(
        self, callback: Callable[[Dict[str, Any]], Awaitable[None]]
    ):
        """Register a callback for when API responses are received.

        Args:
            callback: Async function to call with response data
        """
        self._response_callback = callback
        logger.debug("Response callback registered")

    async def process_touch_event(self) -> bool:
        """Process a touch event and potentially capture an image.

        Returns:
            bool: True if capture was triggered
        """
        current_time = time.time()

        if current_time - self.last_capture_time < self.min_interval_sec:
            return False

        self.last_capture_time = current_time

        asyncio.create_task(self._capture_and_process())
        return True

    async def _capture_and_process(self):
        """Capture image using the initialized picamzero camera and send to API."""
        if not self.camera:
            logger.error("Camera not available for capture.")
            return

        try:
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=True) as tmp_file:
                self.camera.take_photo(tmp_file.name)
                tmp_file.seek(0)
                binary_jpeg_data = tmp_file.read()

            logger.debug("Image captured, sending to API...")
            await self._send_to_api(binary_jpeg_data)

        except Exception as e:
            logger.error(
                f"Error during image capture or processing: {e}", exc_info=True
            )

    async def _send_to_api(self, image_data: bytes):
        """Send image to API and process response."""
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=5)
            ) as session:
                async with session.post(self.api_url, data=image_data) as response:
                    if response.status != 200:
                        logger.error(
                            f"API request failed with status {response.status}"
                        )
                        return

                    response_data = await response.json()
                    logger.info(f"API response received: {response_data}")

                    self.latest_response = response_data

                    if self._response_callback:
                        await self._response_callback(response_data)

                    asyncio.create_task(self._expire_response())

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error(f"API request failed: {e}")
            # Send a random compliment as fallback
            if self.compliments and self._response_callback:
                fallback_compliment = random.choice(self.compliments)
                fallback_response = {"text": fallback_compliment, "fallback": True}
                logger.info(f"Sending fallback compliment: {fallback_compliment}")
                try:
                    await self._response_callback(fallback_response)
                    # We might still want to expire this fallback message
                    asyncio.create_task(self._expire_fallback_response())
                except Exception as cb_err:
                    logger.error(
                        f"Error in fallback response callback: {cb_err}", exc_info=True
                    )
        except Exception as e:
            logger.error(f"Error in API request: {e}", exc_info=True)

    async def _expire_response(self):
        """Clear response after display time."""
        await asyncio.sleep(self.response_display_time)

        if self.latest_response:
            self.latest_response = None

            if self._response_callback:
                await self._response_callback({"text": "", "expired": True})

            logger.debug("Response expired")

    async def _expire_fallback_response(self):
        """Clear fallback response after display time."""
        await asyncio.sleep(self.response_display_time)
        if self._response_callback:
            # Send an empty message to clear the display
            await self._response_callback({"text": "", "expired": True})
            logger.debug("Fallback response expired")

    def get_state(self) -> Dict[str, Any]:
        """Return the current state for persistence."""
        return {"last_capture_time": self.last_capture_time}

    def load_state(self, state_data: Dict[str, Any]):
        """Load state from a dictionary."""
        self.last_capture_time = float(state_data.get("last_capture_time", 0.0))
