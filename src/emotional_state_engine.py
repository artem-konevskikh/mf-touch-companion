"""
Emotional State Engine for touch sensor companion device.

This module manages the emotional state of the device and controls the LED strip.
"""

import logging
import threading
import time
from enum import Enum
from typing import Dict, Optional, Tuple

from src.database import Database, EmotionalState
from src.hardware.led_strip import LedStrip

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class EmotionalStateType(str, Enum):
    """Enum for emotional states."""

    SAD = "sad"
    GLAD = "glad"


class EmotionalStateEngine:
    """Engine for managing the emotional state of the device."""

    # Color mappings for different states
    STATE_COLORS: Dict[EmotionalStateType, Tuple[int, int, int]] = {
        EmotionalStateType.SAD: (0, 0, 255),  # Blue for sad
        EmotionalStateType.GLAD: (255, 140, 0),  # Warm orange for glad
    }

    # Touch count threshold for state transitions
    GLAD_THRESHOLD = 20

    def __init__(
        self,
        database: Database,
        led_strip: LedStrip,
        check_interval: float = 10.0,  # How often to check touch count
        transition_steps: int = 80,  # Steps for color transition
    ) -> None:
        """Initialize the emotional state engine.

        The emotional state changes based on touch count in the last hour:
        - Transitions from sad to glad when there are 20 or more touches in the last hour
        - Transitions from glad to sad when there are less than 20 touches in the last hour

        Args:
            database: The database instance
            led_strip: The LED strip controller
            glad_threshold: Touches per minute to transition to glad state
            sad_threshold: Touches per minute to transition to sad state
            check_interval: How often (in seconds) to check touch frequency
            transition_steps: Number of steps for color transitions
            measure_window: Time window (in seconds) to measure touch frequency
        """
        self.database = database
        self.led_strip = led_strip
        self.check_interval = check_interval
        self.transition_steps = transition_steps
        # Fixed to 1 hour (3600 seconds) for measuring touch count
        self.measure_window = 3600

        # Initialize state from database or default to sad
        try:
            self.current_state = EmotionalStateType(
                self.database.get_current_emotional_state()
            )
        except ValueError:
            logger.warning("Invalid state in database, defaulting to SAD")
            self.current_state = EmotionalStateType.SAD

        self._running = False
        self._state_thread: Optional[threading.Thread] = None

        logger.info(
            f"Emotional state engine initialized with current state: {self.current_state}"
        )

    def start(self) -> None:
        """Start the emotional state engine."""
        if self._running:
            logger.warning("Emotional state engine is already running")
            return

        self._running = True

        # Set initial LED state
        self._update_led_state()

        # Start state monitoring thread
        self._state_thread = threading.Thread(target=self._monitor_state, daemon=True)
        self._state_thread.start()

        logger.info("Emotional state engine started")

    def stop(self) -> None:
        """Stop the emotional state engine."""
        if not self._running:
            logger.warning("Emotional state engine is not running")
            return

        self._running = False

        # Wait for threads to complete
        if self._state_thread:
            self._state_thread.join(timeout=2.0)

        logger.info("Emotional state engine stopped")

    def check_and_update_state(self) -> bool:
        """Check touch count and update emotional state if needed.
        
        This method is designed to be called when a new touch event occurs,
        allowing the state to update immediately when the threshold is reached.
        
        Returns:
            True if the state was changed, False otherwise
        """
        try:
            # Get touch count in the last hour
            touch_count = self.database.get_touch_count_last_hour()
            
            # Check if state transition is needed
            old_state = self.current_state
            state_changed = False

            if (
                self.current_state == EmotionalStateType.SAD
                and touch_count >= self.GLAD_THRESHOLD
            ):
                # Transition to glad state
                self.current_state = EmotionalStateType.GLAD
                logger.info(
                    f"State transition: {old_state} -> {self.current_state} "
                    f"(touch count: {touch_count})"
                )
                self._record_state_change()
                self._update_led_state()
                state_changed = True

            elif (
                self.current_state == EmotionalStateType.GLAD
                and touch_count < self.GLAD_THRESHOLD
            ):
                # Transition to sad state
                self.current_state = EmotionalStateType.SAD
                logger.info(
                    f"State transition: {old_state} -> {self.current_state} "
                    f"(touch count: {touch_count})"
                )
                self._record_state_change()
                self._update_led_state()
                state_changed = True
                
            return state_changed
            
        except Exception as e:
            logger.error(f"Error checking emotional state: {e}", exc_info=True)
            return False

    def _monitor_state(self) -> None:
        """Monitor touch count in the last hour and update emotional state accordingly."""
        while self._running:
            try:
                # Use the same method as for touch events to check and update state
                self.check_and_update_state()
            except Exception as e:
                logger.error(f"Error in emotional state monitoring: {e}", exc_info=True)

            # Wait before next check
            time.sleep(self.check_interval)

    def _record_state_change(self) -> None:
        """Record the state change in the database."""
        try:
            state_event = EmotionalState(
                state=self.current_state.value, timestamp=time.time()
            )
            self.database.add_emotional_state(state_event)
            logger.info(f"Recorded state change to {self.current_state}")
        except Exception as e:
            logger.error(f"Failed to record state change: {e}", exc_info=True)

    def _update_led_state(self) -> None:
        """Update the LED strip based on the current emotional state."""
        # Get color for current state
        color = self.STATE_COLORS[self.current_state]

        try:
            # Change color with smooth transition
            logger.info(f"Changing LED color to {color} for state {self.current_state}")
            self.led_strip.change_color(color, steps=self.transition_steps)
            logger.info(f"LED color changed to {color} for state {self.current_state}")

        except Exception as e:
            logger.error(f"Failed to update LED state: {e}", exc_info=True)


    def get_current_state(self) -> EmotionalStateType:
        """Get the current emotional state.

        Returns:
            The current emotional state
        """
        return self.current_state

    def get_state_emoji(self) -> str:
        """Get an emoji representation of the current emotional state.

        Returns:
            An emoji string representing the current state
        """
        if self.current_state == EmotionalStateType.GLAD:
            return "(◠‿◠)"
        else:
            return "(︶︹︶)"

    def force_state(self, state: EmotionalStateType) -> None:
        """Force a particular emotional state.

        Args:
            state: The emotional state to set
        """
        if state not in EmotionalStateType:
            logger.error(f"Invalid emotional state: {state}", exc_info=True)
            return

        logger.info(f"Forcing emotional state to {state}")
        self.current_state = state
        self._record_state_change()
        self._update_led_state()
