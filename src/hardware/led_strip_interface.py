"""
LED Strip Interface for Touch Companion Application

This module provides an interface to the RGB LED strip using the provided
LedStrip class implementation with pi5neo library.
"""

import time
import logging
import threading
from pi5neo import Pi5Neo

logger = logging.getLogger("hardware.led_strip")


class LEDStrip:
    """Interface with the RGB LED strip using Pi5Neo."""

    def __init__(self, device="/dev/pi5neo0", num_leds=16, frequency=800000):
        """
        Initialize the LED strip interface.

        Args:
            device: Device path for the Pi5Neo
            num_leds: Number of LEDs in the strip
            frequency: LED strip signal frequency
        """
        # Initialize LED strip directly in constructor
        self.neo = Pi5Neo(device, num_leds, frequency)
        self.current_color = (0, 0, 0)  # Default color is off
        self.steps = 100  # Default steps for transitions
        self._shimmer_active = False

        # Clear the strip initially
        self.clear()
        logger.info("LED strip initialized successfully")

    def set_color(self, r, g, b):
        """
        Set all LEDs to the specified RGB color immediately.

        Args:
            r: Red component (0-255)
            g: Green component (0-255)
            b: Blue component (0-255)
        """
        if self.neo is None:
            logger.warning("LED strip not initialized")
            return

        try:
            # Stop any active shimmering
            self._shimmer_active = False

            # Store current color
            self.current_color = (r, g, b)

            # Set all LEDs to the same color
            for led in range(self.neo.num_leds):
                self.neo.set_led_color(led, r, g, b)
            self.neo.update_strip()

        except Exception as e:
            logger.error(f"Error setting LED strip color: {str(e)}")

    def change_color(self, color, steps=None):
        """
        Change the color with a smooth transition.

        Args:
            color: Target color as (R, G, B) tuple
            steps: Number of steps for the transition (uses self.steps if None)
        """
        if self.neo is None:
            logger.warning("LED strip not initialized")
            return

        try:
            # Stop any active shimmering
            self._shimmer_active = False

            # Use default steps if not specified
            if steps is None:
                steps = self.steps
            else:
                self.steps = steps

            # Perform smooth transition
            for step in range(steps):
                for led in range(self.neo.num_leds):
                    transition_color = tuple(
                        int(
                            self.current_color[c]
                            + ((color[c] - self.current_color[c]) * (step / steps))
                        )
                        for c in range(3)
                    )
                    self.neo.set_led_color(led, *transition_color)
                self.neo.update_strip()
                time.sleep(0.01)

            self.current_color = color

        except Exception as e:
            logger.error(f"Error during color transition: {str(e)}")

    def shimmer(self, color, speed=0.1):
        """
        Create a shimmering effect with the specified base color.

        Args:
            color: Base color as (R, G, B) tuple
            speed: Speed of shimmer effect (seconds between updates)
        """
        if self.neo is None:
            logger.warning("LED strip not initialized")
            return

        try:
            # Stop any existing shimmer thread
            self._shimmer_active = False

            # Update current color
            self.current_color = color

            # Start new shimmer in a separate thread
            self._shimmer_active = True
            shimmer_thread = threading.Thread(
                target=self._do_shimmer, args=(color, speed), daemon=True
            )
            shimmer_thread.start()

        except Exception as e:
            logger.error(f"Error starting shimmer effect: {str(e)}")

    def _do_shimmer(self, color, speed):
        """Internal method to perform the shimmer effect in a separate thread."""
        import random
        import math

        try:
            # Initialize each LED with a different phase to create more natural twinkling
            led_phases = [
                random.uniform(0, 2 * math.pi) for _ in range(self.neo.num_leds)
            ]
            led_speeds = [random.uniform(0.3, 1.0) for _ in range(self.neo.num_leds)]

            while self._shimmer_active:
                # Update each LED independently
                for led in range(self.neo.num_leds):
                    # Create a more pronounced shimmer effect (0.5 to 1.5 range)
                    shimmer_factor = 0.7 + math.sin(led_phases[led]) * 0.5

                    # Apply the shimmer factor to create a unique color for each LED
                    shimmer_color = tuple(
                        max(0, min(255, int(c * shimmer_factor))) for c in color
                    )

                    # Update the LED with its unique color
                    self.neo.set_led_color(led, *shimmer_color)

                    # Update the phase for this LED
                    led_phases[led] += 0.3 * led_speeds[led]

                # Update the entire strip at once
                self.neo.update_strip()
                time.sleep(speed)

        except Exception as e:
            logger.error(f"Error in shimmer effect: {str(e)}")
            self._shimmer_active = False

    def set_intensity(self, intensity, color=None):
        """
        Set the brightness/intensity of the LEDs.

        Args:
            intensity: Value between 0.0 (off) and 1.0 (full brightness)
            color: Color to apply intensity to, or None to use current color

        Returns:
            The scaled color that was applied
        """
        if self.neo is None:
            logger.warning("LED strip not initialized")
            return None

        try:
            # Ensure intensity is in valid range
            intensity = max(0.0, min(1.0, intensity))

            # Determine which color to scale
            color_to_scale = color if color is not None else self.current_color

            # Apply intensity to create scaled color
            scaled_color = tuple(int(c * intensity) for c in color_to_scale)

            # Set all LEDs to the scaled color
            for led in range(self.neo.num_leds):
                self.neo.set_led_color(led, *scaled_color)
            self.neo.update_strip()

            # Update current color
            self.current_color = scaled_color
            return scaled_color

        except Exception as e:
            logger.error(f"Error setting LED intensity: {str(e)}")
            return None

    def clear(self):
        """Turn off all LEDs."""
        if self.neo is None:
            logger.warning("LED strip not initialized")
            return

        try:
            # Stop any active shimmering
            self._shimmer_active = False

            # Fill strip with black (all off)
            self.neo.fill_strip(0, 0, 0)
            self.neo.update_strip()

            # Update current color
            self.current_color = (0, 0, 0)

        except Exception as e:
            logger.error(f"Error clearing LED strip: {str(e)}")
