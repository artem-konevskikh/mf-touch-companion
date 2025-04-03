"""
Server-Sent Events implementation for Touch Companion Application

This module provides:
- Custom SSE response class for FastAPI
- Event manager for broadcasting events to connected clients
- Utilities for formatting and sending SSE data
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Dict, Any, AsyncGenerator, Optional, Callable

from fastapi import Request
from starlette.responses import Response
from starlette.background import BackgroundTask

# Configure logging
logger = logging.getLogger("sse")


class SSEResponse(Response):
    """
    Server-Sent Events response for FastAPI.

    This response type sets appropriate headers and handles the
    streaming of SSE events to the client.
    """

    media_type = "text/event-stream"

    def __init__(
        self,
        content: AsyncGenerator,
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
        media_type: Optional[str] = None,
        background: Optional[BackgroundTask] = None,
    ):
        """
        Initialize the SSE response.

        Args:
            content: Async generator yielding events
            status_code: HTTP status code
            headers: HTTP headers
            media_type: Response content type
            background: Background task
        """
        super().__init__(
            content=content,
            status_code=status_code,
            headers=headers,
            media_type=media_type,
            background=background,
        )

        # Set SSE specific headers
        if self.headers is None:
            self.headers = {}

        self.headers["Cache-Control"] = "no-cache"
        self.headers["Connection"] = "keep-alive"
        self.headers["X-Accel-Buffering"] = "no"  # Disable Nginx buffering

    async def __call__(self, scope, receive, send) -> None:
        """Process the response when called by the ASGI server."""

        async def send_event(event: dict) -> None:
            """Format and send an SSE event."""
            event_name = event.get("event", "message")
            data = event.get("data", {})

            # Convert data to JSON
            if not isinstance(data, str):
                data = json.dumps(data)

            # Format the SSE message
            message = f"event: {event_name}\ndata: {data}\n\n"

            # Send the message
            await send(
                {
                    "type": "http.response.body",
                    "body": message.encode("utf-8"),
                    "more_body": True,
                }
            )

        # Send response headers
        await send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": [
                    (k.encode("utf-8"), v.encode("utf-8"))
                    for k, v in self.headers.items()
                ],
            }
        )

        # Send initial keep-alive comment
        await send(
            {
                "type": "http.response.body",
                "body": b": keep-alive\n\n",
                "more_body": True,
            }
        )

        # Process events from the generator
        try:
            async for event in self.content:
                await send_event(event)

                # Check if client has disconnected
                if await scope.get("state", {}).get("disconnected", False):
                    break

            # Send end of response
            await send({"type": "http.response.body", "body": b"", "more_body": False})

        except Exception as e:
            logger.error(f"Error in SSE stream: {str(e)}")

            # Send error event before closing
            error_event = {
                "event": "error",
                "data": {"message": "Stream error occurred"},
            }
            await send_event(error_event)

            # Close the response
            await send({"type": "http.response.body", "body": b"", "more_body": False})

            # Re-raise the exception
            raise


class EventManager:
    """
    Manages event broadcasting to SSE clients.

    This class handles:
    - Client registration and disconnection
    - Broadcasting events to all clients
    - Periodic keep-alive messages
    """

    def __init__(self, keep_alive_interval: int = 30):
        """
        Initialize the event manager.

        Args:
            keep_alive_interval: Seconds between keep-alive messages
        """
        self.clients: Dict[str, asyncio.Queue] = {}
        self.keep_alive_interval = keep_alive_interval
        self.keep_alive_task = None

        # Start keep-alive task
        self._start_keep_alive()

    def register_client(self, queue: asyncio.Queue) -> str:
        """
        Register a new client.

        Args:
            queue: Queue to send events to this client

        Returns:
            Unique client ID
        """
        client_id = str(uuid.uuid4())
        self.clients[client_id] = queue
        logger.debug(
            f"Client {client_id} connected, total clients: {len(self.clients)}"
        )
        return client_id

    def unregister_client(self, client_id: str) -> None:
        """
        Unregister a client when they disconnect.

        Args:
            client_id: Client ID to remove
        """
        if client_id in self.clients:
            del self.clients[client_id]
            logger.debug(
                f"Client {client_id} disconnected, remaining clients: {len(self.clients)}"
            )

    def emit(self, event: str, data: Any) -> None:
        """
        Emit an event to all connected clients.

        Args:
            event: Event name
            data: Event data (will be JSON serialized)
        """
        if not self.clients:
            return  # No clients connected

        event_payload = {"event": event, "data": data}

        # Send to all clients
        for client_id, queue in list(self.clients.items()):
            try:
                # Try to put event in queue, skip if full
                if queue.full():
                    logger.warning(f"Queue full for client {client_id}, event dropped")
                else:
                    queue.put_nowait(event_payload)
            except Exception as e:
                logger.error(f"Error sending event to client {client_id}: {str(e)}")
                # Remove problematic client
                self.unregister_client(client_id)

    def _start_keep_alive(self) -> None:
        """Start the keep-alive task."""
        if self.keep_alive_task is None or self.keep_alive_task.done():
            self.keep_alive_task = asyncio.create_task(self._keep_alive_loop())

    async def _keep_alive_loop(self) -> None:
        """Send periodic keep-alive messages to all clients."""
        try:
            while True:
                # Wait for interval
                await asyncio.sleep(self.keep_alive_interval)

                # Send keep-alive to all clients
                timestamp = int(time.time())
                self.emit("keep-alive", {"timestamp": timestamp})

        except asyncio.CancelledError:
            # Task was cancelled, clean up
            pass
        except Exception as e:
            logger.error(f"Error in keep-alive loop: {str(e)}")
