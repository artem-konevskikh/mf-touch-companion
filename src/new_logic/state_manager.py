import time
from src.hardware.led_strip import LedStrip


class StateManager:
    """Manages the sad/glad state based on touch counts and controls the LED strip."""

    SAD_COLOR = (0, 0, 255)  # Blue
    GLAD_COLOR = (255, 0, 0)  # Yellow
    TRANSITION_STEPS = 50

    def __init__(self, led_strip: LedStrip, touch_threshold=5):
        """Initialize the StateManager.

        Args:
            led_strip: An instance of the LedStrip class.
            touch_threshold: The number of touches required to switch to the glad state.
        """
        self.led_strip = led_strip
        self.touch_threshold = touch_threshold
        self.is_glad = False  # Start in the sad state
        self._initialize_leds()

    def _initialize_leds(self):
        """Set the initial LED state (sad)."""
        print("Initializing LEDs to SAD state.")
        self.led_strip.change_color(self.SAD_COLOR, steps=self.TRANSITION_STEPS)

    def update_state(self, touch_count_last_hour):
        """Updates the state based on the touch count.

        Args:
            touch_count_last_hour: The number of touches in the last hour.
        """
        # print(f"Updating state with touch count: {touch_count_last_hour}") # Debugging
        should_be_glad = touch_count_last_hour >= self.touch_threshold

        if should_be_glad and not self.is_glad:
            print(
                f"Touch threshold ({self.touch_threshold}) reached. Changing to GLAD state."
            )
            self.led_strip.change_color(self.GLAD_COLOR, steps=self.TRANSITION_STEPS)
            self.is_glad = True
        elif not should_be_glad and self.is_glad:
            print(
                f"Touch count ({touch_count_last_hour}) below threshold. Changing back to SAD state."
            )
            self.led_strip.change_color(self.SAD_COLOR, steps=self.TRANSITION_STEPS)
            self.is_glad = False
        # else: # Debugging
        # state = "GLAD" if self.is_glad else "SAD"
        # print(f"State remains {state}.")


# Example Usage (requires LedStrip instance)
if __name__ == "__main__":
    # This is a placeholder for testing; requires actual hardware setup
    print("StateManager example - requires hardware setup.")
    # try:
    #     # Replace with your actual LED strip configuration
    #     leds = LedStrip(device='/dev/spidev0.0', num_leds=60, frequency=800000)
    #     manager = StateManager(leds, touch_threshold=3)

    #     # Simulate touch counts
    #     manager.update_state(0)
    #     time.sleep(2)
    #     manager.update_state(2)
    #     time.sleep(2)
    #     manager.update_state(5) # Should turn glad
    #     time.sleep(2)
    #     manager.update_state(4) # Should turn sad
    #     time.sleep(2)

    # except Exception as e:
    #     print(f"Error during StateManager example: {e}")
    # finally:
    #     if 'leds' in locals():
    #         leds.clear()
