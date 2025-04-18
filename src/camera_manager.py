#!/usr/bin/env python3
"""
Camera Manager Module - Simplified.

Handles camera capture and API interactions with minimal complexity.
"""

import asyncio
import cv2
import logging
import time
from typing import Any, Awaitable, Callable, Dict, Optional

import aiohttp

# Configure logger
logger = logging.getLogger("touch_companion.camera_manager")


class CameraManager:
    """Simplified manager for camera operations and API interactions."""

    def __init__(
        self,
        camera_device: int = 0,
        api_url: str = "https://art.ycloud.eazify.net:8443/comp",
        min_interval_sec: int = 5,
        response_display_time: int = 120,
    ):
        """Initialize the camera manager.

        Args:
            camera_device: Camera device index
            api_url: API endpoint URL
            min_interval_sec: Minimum seconds between captures
            response_display_time: How long to display responses
        """
        self.camera_device = camera_device
        self.api_url = api_url
        self.min_interval_sec = min_interval_sec
        self.response_display_time = response_display_time
        self.last_capture_time: float = 0.0
        self.latest_response: Optional[Dict[str, Any]] = None
        self._response_callback: Optional[
            Callable[[Dict[str, Any]], Awaitable[None]]
        ] = None

    def register_response_callback(
        self, callback: Callable[[Dict[str, Any]], Awaitable[None]]
    ):
        """Register a callback for when API responses are received.

        Args:
            callback: Async function to call with response data
        """
        self._response_callback = callback
        logger.info("Response callback registered")

    async def process_touch_event(self) -> bool:
        """Process a touch event and potentially capture an image.

        Returns:
            bool: True if capture was triggered
        """
        current_time = time.time()

        # Skip if not enough time has passed
        if current_time - self.last_capture_time < self.min_interval_sec:
            return False

        # Update time first to prevent rapid calls
        self.last_capture_time = current_time

        # Start capture and API call in background
        asyncio.create_task(self._capture_and_process())
        return True

    async def _capture_and_process(self):
        """Capture image and send to API in background."""
        try:
            # Open camera (and close it when done)
            camera = cv2.VideoCapture(self.camera_device)
            if not camera.isOpened():
                logger.error(f"Failed to open camera device {self.camera_device}")
                return

            try:
                # Capture frame
                ret, frame = camera.read()
                if not ret or frame is None:
                    logger.error("Failed to capture image")
                    return

                logger.info("Image captured, sending to API...")

                # Convert to JPEG
                success, buffer = cv2.imencode(".jpg", frame)
                if not success:
                    logger.error("Failed to encode image")
                    return

                # Send to API
                binary_jpeg = buffer.tobytes()
                await self._send_to_api(binary_jpeg)

            finally:
                # Always release camera
                camera.release()

        except Exception as e:
            logger.error(f"Error in camera capture: {e}", exc_info=True)

    async def _send_to_api(self, image_data: bytes):
        """Send image to API and process response."""
        try:
            # Use a short timeout to avoid hanging
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            ) as session:
                async with session.post(self.api_url, data=image_data) as response:
                    if response.status != 200:
                        logger.error(
                            f"API request failed with status {response.status}"
                        )
                        return

                    # Process response
                    response_data = await response.json()
                    logger.info(f"API response received: {response_data}")

                    # Store response
                    self.latest_response = response_data

                    # Notify callback
                    if self._response_callback:
                        await self._response_callback(response_data)

                    # Schedule expiration
                    asyncio.create_task(self._expire_response())

        except asyncio.TimeoutError:
            logger.error("API request timed out")
        except Exception as e:
            logger.error(f"Error in API request: {e}", exc_info=True)

    async def _expire_response(self):
        """Clear response after display time."""
        await asyncio.sleep(self.response_display_time)

        # Clear and notify
        if self.latest_response:
            self.latest_response = None

            # Notify about expiration
            if self._response_callback:
                await self._response_callback({"text": "", "expired": True})

            logger.debug("Response expired")

    def release_camera(self):
        """Release camera resources (not used in this implementation)."""
        # Camera is only opened when needed, no need to explicitly release
        pass

    def get_state(self) -> Dict[str, Any]:
        """Return the current state for persistence."""
        return {"last_capture_time": self.last_capture_time}

    def load_state(self, state_data: Dict[str, Any]):
        """Load state from a dictionary."""
        self.last_capture_time = float(state_data.get("last_capture_time", 0.0))
