"""
Emotional State Engine for Touch Companion Application

This module:
- Interfaces with custom LED strip control code
- Determines emotional state based on touch frequency
- Manages state transitions between sad and glad
- Controls color transition effects for smooth state changes
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Callable
from enum import Enum, auto

# Import your custom LED strip interface
# This is a placeholder - you'll replace with your actual implementation
from hardware.led_strip_interface import LEDStrip

# Import database module
from modules.database import db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("data/emotional_state.log"), logging.StreamHandler()],
)
logger = logging.getLogger("emotional_state")


class EmotionalState(Enum):
    """Emotional states for the companion device."""

    SAD = auto()
    GLAD = auto()


class EmotionalStateEngine:
    """Manages the emotional state of the companion device based on touch events."""

    def __init__(self):
        """Initialize the emotional state engine."""
        self.led_strip = None
        self.current_state = EmotionalState.SAD
        self.state_changed_callbacks: Set[Callable] = set()

        # State determination parameters
        self.touch_buffer: List[float] = []  # Timestamps of recent touches
        self.buffer_max_size = 20  # Max number of touches to keep
        self.buffer_max_age = 300  # Max age of touches in seconds (5 minutes)

        # Thresholds for state transitions
        self.sad_to_glad_threshold = 10  # Min touches in buffer to transition to glad
        self.glad_to_sad_threshold = 3  # Max touches in buffer to transition to sad

        # Transition effect parameters
        self.transition_duration = 5.0  # Transition duration in seconds
        self.transition_steps = 50  # Number of steps for smooth transition
        self.transition_task = None  # Task for handling transition effects

        # LED color configurations
        self.sad_color = (0, 0, 255)  # Blue for sad
        self.glad_color = (255, 255, 0)  # Yellow for glad
        self.current_color = self.sad_color  # Current displayed color

        # Flag to track if we're in a transition
        self.in_transition = False

    async def initialize(self) -> bool:
        """
        Initialize the LED strip and load the current emotional state.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Initialize LED strip
            self.led_strip = LEDStrip()
            await asyncio.to_thread(self.led_strip.initialize)

            # Load current state from database
            db_state = await db.get_current_emotional_state()
            self.current_state = (
                EmotionalState.GLAD if db_state == "glad" else EmotionalState.SAD
            )

            # Set initial color based on current state
            if self.current_state == EmotionalState.SAD:
                self.current_color = self.sad_color
                await asyncio.to_thread(self.led_strip.set_color, *self.sad_color)
            else:
                self.current_color = self.glad_color
                await asyncio.to_thread(self.led_strip.set_color, *self.glad_color)

            logger.info(
                f"Emotional state engine initialized with state: {self.current_state.name}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to initialize emotional state engine: {str(e)}")
            return False

    def register_state_changed_callback(self, callback: Callable) -> None:
        """
        Register a callback to be called when emotional state changes.

        Args:
            callback: Function to call with new state information
        """
        self.state_changed_callbacks.add(callback)

    def unregister_state_changed_callback(self, callback: Callable) -> None:
        """Remove a previously registered callback."""
        if callback in self.state_changed_callbacks:
            self.state_changed_callbacks.remove(callback)

    async def process_touch_event(self, duration_ms: int) -> None:
        """
        Process a new touch event and update emotional state if needed.

        Args:
            duration_ms: Duration of the touch in milliseconds
        """
        current_time = time.time()

        # Add current timestamp to buffer
        self.touch_buffer.append(current_time)

        # Remove old touches from buffer
        cutoff_time = current_time - self.buffer_max_age
        self.touch_buffer = [t for t in self.touch_buffer if t >= cutoff_time]

        # Ensure buffer doesn't exceed max size
        if len(self.touch_buffer) > self.buffer_max_size:
            self.touch_buffer = self.touch_buffer[-self.buffer_max_size :]

        # Determine if state should change
        buffer_size = len(self.touch_buffer)

        if (
            self.current_state == EmotionalState.SAD
            and buffer_size >= self.sad_to_glad_threshold
        ):
            await self._change_state(EmotionalState.GLAD)
        elif (
            self.current_state == EmotionalState.GLAD
            and buffer_size <= self.glad_to_sad_threshold
        ):
            await self._change_state(EmotionalState.SAD)

    async def _change_state(self, new_state: EmotionalState) -> None:
        """
        Change the emotional state and trigger transition effects.

        Args:
            new_state: The new emotional state to transition to
        """
        if self.current_state == new_state:
            return

        old_state = self.current_state
        self.current_state = new_state

        # Update state in database
        state_str = "glad" if new_state == EmotionalState.GLAD else "sad"
        await db.update_emotional_state(state_str)

        logger.info(
            f"Emotional state changed from {old_state.name} to {new_state.name}"
        )

        # Start color transition
        if self.transition_task and not self.transition_task.done():
            self.transition_task.cancel()

        self.transition_task = asyncio.create_task(
            self._transition_color(
                self.sad_color if old_state == EmotionalState.GLAD else self.glad_color,
                self.glad_color if new_state == EmotionalState.GLAD else self.sad_color,
            )
        )

        # Notify callbacks of state change
        state_info = {
            "old_state": old_state.name.lower(),
            "new_state": new_state.name.lower(),
            "timestamp": datetime.now().isoformat(),
        }

        for callback in self.state_changed_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(state_info)
                else:
                    callback(state_info)
            except Exception as e:
                logger.error(f"Error in state change callback: {str(e)}")

    async def _transition_color(self, start_color: tuple, end_color: tuple) -> None:
        """
        Perform a smooth color transition.

        Args:
            start_color: (R, G, B) tuple for starting color
            end_color: (R, G, B) tuple for ending color
        """
        self.in_transition = True

        try:
            # Use LED strip's built-in transition function
            await asyncio.to_thread(
                self.led_strip.set_color_with_transition,
                end_color[0],
                end_color[1],
                end_color[2],
                self.transition_steps,
            )
            self.current_color = end_color

        except asyncio.CancelledError:
            # Transition was interrupted, immediately set final color
            if self.current_state == EmotionalState.SAD:
                await asyncio.to_thread(self.led_strip.set_color, *self.sad_color)
                self.current_color = self.sad_color
            else:
                await asyncio.to_thread(self.led_strip.set_color, *self.glad_color)
                self.current_color = self.glad_color

        except Exception as e:
            logger.error(f"Error during color transition: {str(e)}")

        finally:
            self.in_transition = False

    async def get_current_state(self) -> str:
        """
        Get the current emotional state as a string.

        Returns:
            "glad" or "sad"
        """
        return "glad" if self.current_state == EmotionalState.GLAD else "sad"

    def get_state_info(self) -> Dict:
        """
        Get information about the current emotional state.

        Returns:
            Dictionary with state information
        """
        return {
            "state": self.current_state.name.lower(),
            "in_transition": self.in_transition,
            "touch_count": len(self.touch_buffer),
            "current_color": self.current_color,
        }
