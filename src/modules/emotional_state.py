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
from datetime import datetime
from typing import Dict, List, Set, Callable
from enum import Enum, auto

from src.hardware.led_strip_interface import LEDStrip
from src.modules.database import db
from src.config import EMOTIONAL_STATE_SETTINGS, LED_SETTINGS

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
        self.led_strip = LEDStrip(
            num_leds=LED_SETTINGS["LED_COUNT"],
            frequency=800000,  # Default frequency
        )
        self.current_state = EmotionalState.SAD
        self.state_changed_callbacks: Set[Callable] = set()

        # State determination parameters from config
        self.touch_buffer: List[float] = []  # Timestamps of recent touches
        self.buffer_max_size = EMOTIONAL_STATE_SETTINGS["TOUCH_BUFFER_MAX_SIZE"]
        self.buffer_max_age = EMOTIONAL_STATE_SETTINGS["TOUCH_BUFFER_MAX_AGE_SEC"]

        # Thresholds for state transitions from config
        self.sad_to_glad_threshold = EMOTIONAL_STATE_SETTINGS["SAD_TO_GLAD_THRESHOLD"]
        self.glad_to_sad_threshold = EMOTIONAL_STATE_SETTINGS["GLAD_TO_SAD_THRESHOLD"]

        # Transition effect parameters from config
        self.transition_duration = EMOTIONAL_STATE_SETTINGS["TRANSITION_DURATION_SEC"]
        self.transition_steps = EMOTIONAL_STATE_SETTINGS["TRANSITION_STEPS"]
        self.transition_task = None  # Task for handling transition effects

        # LED color configurations from config
        self.sad_color = EMOTIONAL_STATE_SETTINGS["SAD_COLOR"]
        self.glad_color = EMOTIONAL_STATE_SETTINGS["GLAD_COLOR"]
        self.current_color = self.sad_color  # Current displayed color

        # Flag to track if we're in a transition
        self.in_transition = False

    async def initialize(self) -> bool:
        """
        Initialize and load the current emotional state.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
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

    async def process_touch_event(self) -> None:
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
            # Ensure LED strip is initialized
            if self.led_strip is None:
                logger.error("LED strip not initialized during transition attempt")
                return

            # Set the number of steps for the transition
            self.led_strip.steps = self.transition_steps

            # Use LED strip's built-in change_color method with proper error handling
            logger.info(f"Starting color transition from {start_color} to {end_color}")
            await asyncio.to_thread(
                self.led_strip.change_color, end_color, self.transition_steps
            )
            self.current_color = end_color
            logger.info(f"Color transition completed to {end_color}")

        except asyncio.CancelledError:
            # Transition was interrupted, immediately set final color
            logger.info("Color transition was cancelled, setting final color directly")
            if self.current_state == EmotionalState.SAD:
                await asyncio.to_thread(self.led_strip.set_color, *self.sad_color)
                self.current_color = self.sad_color
            else:
                await asyncio.to_thread(self.led_strip.set_color, *self.glad_color)
                self.current_color = self.glad_color

        except Exception as e:
            logger.error(f"Error during color transition: {str(e)}")
            # Attempt to set the final color directly as a fallback
            try:
                target_color = (
                    self.sad_color
                    if self.current_state == EmotionalState.SAD
                    else self.glad_color
                )
                await asyncio.to_thread(self.led_strip.set_color, *target_color)
                self.current_color = target_color
                logger.info(f"Fallback: Set color directly to {target_color}")
            except Exception as fallback_error:
                logger.error(
                    f"Fallback color setting also failed: {str(fallback_error)}"
                )

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
