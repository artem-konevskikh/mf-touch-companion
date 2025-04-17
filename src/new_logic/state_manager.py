#!/usr/bin/env python3
"""
State Manager Module.

Manages the sad/glad state based on touch counts and controls the LED strip.
"""

import logging
from typing import Tuple

from src.hardware.led_strip import LedStrip

# Configure logger
logger = logging.getLogger("touch_companion.state_manager")


class StateManager:
    """Manages the sad/glad state based on touch counts and controls the LED strip."""

    def __init__(
        self,
        led_strip: LedStrip,
        touch_threshold: int = 5,
        sad_color: Tuple[int, int, int] = (0, 0, 255),  # Blue
        glad_color: Tuple[int, int, int] = (255, 0, 0),  # Red
        transition_steps: int = 50,
    ):
        """Initialize the StateManager.

        Args:
            led_strip: An instance of the LedStrip class
            touch_threshold: The number of touches required to switch to the glad state
            sad_color: RGB color tuple for sad state
            glad_color: RGB color tuple for glad state
            transition_steps: Number of steps for color transitions
        """
        self.led_strip = led_strip
        self.touch_threshold = touch_threshold
        self.sad_color = sad_color
        self.glad_color = glad_color
        self.transition_steps = transition_steps
        self.is_glad = False  # Start in the sad state
        self._initialize_leds()

    def _initialize_leds(self) -> None:
        """Set the initial LED state (sad)."""
        logger.info("Initializing LEDs to SAD state")
        self.led_strip.change_color(self.sad_color, steps=self.transition_steps)

    def update_state(self, touch_count_last_hour: int) -> None:
        """Update the state based on the touch count.

        Args:
            touch_count_last_hour: The number of touches in the last hour
        """
        should_be_glad = touch_count_last_hour >= self.touch_threshold

        if should_be_glad and not self.is_glad:
            logger.info(
                f"Touch threshold ({self.touch_threshold}) reached. Changing to GLAD state"
            )
            self.led_strip.change_color(self.glad_color, steps=self.transition_steps)
            self.is_glad = True
        elif not should_be_glad and self.is_glad:
            logger.info(
                f"Touch count ({touch_count_last_hour}) below threshold. Changing back to SAD state"
            )
            self.led_strip.change_color(self.sad_color, steps=self.transition_steps)
            self.is_glad = False


# Example Usage (requires LedStrip instance)
if __name__ == "__main__":
    # Configure logging for standalone testing
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger.info("StateManager example - requires hardware setup")

    # Example code below is commented out as it requires actual hardware
    # try:
    #     # Replace with your actual LED strip configuration
    #     leds = LedStrip(device='/dev/spidev0.0', num_leds=60, frequency=800000)
    #     manager = StateManager(leds, touch_threshold=3)
    #
    #     # Simulate touch counts
    #     manager.update_state(0)
    #     time.sleep(2)
    #     manager.update_state(2)
    #     time.sleep(2)
    #     manager.update_state(5)  # Should turn glad
    #     time.sleep(2)
    #     manager.update_state(4)  # Should turn sad
    #     time.sleep(2)
    #
    # except Exception as e:
    #     logger.error(f"Error during StateManager example: {e}", exc_info=True)
    # finally:
    #     if 'leds' in locals():
    #         leds.clear()
    #         logger.info("LED strip cleared")
