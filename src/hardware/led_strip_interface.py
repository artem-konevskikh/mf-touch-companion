"""
LED Strip Interface for Touch Companion Application

This module provides an interface to the RGB LED strip
using the provided custom implementation with pi5neo library.
"""

import time
import logging
import threading
from pi5neo import Pi5Neo

logger = logging.getLogger("hardware.led_strip")


class LEDStrip:
    """Interface with the RGB LED strip using Pi5Neo."""

    def __init__(self, device="/dev/pi5neo0", num_pixels=16, frequency=800000):
        """
        Initialize the LED strip interface.

        Args:
            device: Device path for the Pi5Neo
            num_pixels: Number of LEDs in the strip
            frequency: LED strip signal frequency
        """
        self.device = device
        self.num_pixels = num_pixels
        self.frequency = frequency
        self.led_strip = None
        self.current_color = (0, 0, 0)
        self.initialized = False
        self._shimmer_thread = None
        self._shimmer_active = False

    def initialize(self):
        """Initialize the LED strip."""
        try:
            # Create LED strip instance
            self.led_strip = Pi5Neo(self.device, self.num_pixels, self.frequency)

            # Turn off all LEDs initially
            for led in range(self.num_pixels):
                self.led_strip.set_led_color(led, 0, 0, 0)
            self.led_strip.update_strip()

            self.initialized = True
            logger.info("LED strip initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize LED strip: {str(e)}")
            self.initialized = False

        return self.initialized

    def set_color(self, r, g, b):
        """
        Set all LEDs to the specified RGB color.

        Args:
            r: Red component (0-255)
            g: Green component (0-255)
            b: Blue component (0-255)
        """
        if not self.initialized:
            logger.warning("Attempting to control uninitialized LED strip")
            return

        try:
            # Stop any active shimmering
            self._shimmer_active = False
            if self._shimmer_thread and self._shimmer_thread.is_alive():
                self._shimmer_thread.join(timeout=1.0)

            # Store current color
            self.current_color = (r, g, b)

            # Set all pixels to the same color
            for led in range(self.num_pixels):
                self.led_strip.set_led_color(led, r, g, b)
            self.led_strip.update_strip()

        except Exception as e:
            logger.error(f"Error setting LED strip color: {str(e)}")

    def set_color_with_transition(self, r, g, b, steps=100):
        """
        Set all LEDs to the specified RGB color with a smooth transition.

        Args:
            r: Red component (0-255)
            g: Green component (0-255)
            b: Blue component (0-255)
            steps: Number of steps for the transition
        """
        if not self.initialized:
            logger.warning("Attempting to control uninitialized LED strip")
            return

        try:
            # Stop any active shimmering
            self._shimmer_active = False
            if self._shimmer_thread and self._shimmer_thread.is_alive():
                self._shimmer_thread.join(timeout=1.0)

            # Start a new thread for the transition
            target_color = (r, g, b)
            transition_thread = threading.Thread(
                target=self._transition_color,
                args=(self.current_color, target_color, steps),
                daemon=True,
            )
            transition_thread.start()

        except Exception as e:
            logger.error(f"Error starting color transition: {str(e)}")

    def _transition_color(self, start_color, end_color, steps):
        """
        Perform a smooth color transition.

        Args:
            start_color: Starting RGB color tuple
            end_color: Target RGB color tuple
            steps: Number of steps for the transition
        """
        try:
            for step in range(steps):
                # Calculate interpolated color
                r = int(
                    start_color[0] + ((end_color[0] - start_color[0]) * (step / steps))
                )
                g = int(
                    start_color[1] + ((end_color[1] - start_color[1]) * (step / steps))
                )
                b = int(
                    start_color[2] + ((end_color[2] - start_color[2]) * (step / steps))
                )

                # Set all LEDs to the interpolated color
                for led in range(self.num_pixels):
                    self.led_strip.set_led_color(led, r, g, b)
                self.led_strip.update_strip()

                # Update current color
                self.current_color = (r, g, b)

                # Short delay between steps
                time.sleep(0.01)

            # Ensure final color is set exactly
            for led in range(self.num_pixels):
                self.led_strip.set_led_color(
                    led, end_color[0], end_color[1], end_color[2]
                )
            self.led_strip.update_strip()

            self.current_color = end_color

        except Exception as e:
            logger.error(f"Error during color transition: {str(e)}")

    def shimmer(self, r, g, b, speed=0.1):
        """
        Create a shimmering effect with the specified base color.

        Args:
            r: Red component (0-255)
            g: Green component (0-255)
            b: Blue component (0-255)
            speed: Speed of shimmer effect (seconds between updates)
        """
        if not self.initialized:
            logger.warning("Attempting to control uninitialized LED strip")
            return

        try:
            # Stop any existing shimmer
            self._shimmer_active = False
            if self._shimmer_thread and self._shimmer_thread.is_alive():
                self._shimmer_thread.join(timeout=1.0)

            # Start new shimmer thread
            self._shimmer_active = True
            self.current_color = (r, g, b)
            self._shimmer_thread = threading.Thread(
                target=self._shimmer_thread_func, args=((r, g, b), speed), daemon=True
            )
            self._shimmer_thread.start()

        except Exception as e:
            logger.error(f"Error starting shimmer effect: {str(e)}")

    def _shimmer_thread_func(self, color, speed):
        """
        Thread function for shimmer effect.

        Args:
            color: Base RGB color tuple
            speed: Speed of effect
        """
        import random
        import math

        try:
            # Initialize each LED with a different phase
            led_phases = [
                random.uniform(0, 2 * math.pi) for _ in range(self.num_pixels)
            ]
            led_speeds = [random.uniform(0.3, 1.0) for _ in range(self.num_pixels)]

            while self._shimmer_active:
                # Update each LED independently
                for led in range(self.num_pixels):
                    # Create a shimmer effect (0.7 to 1.2 range)
                    shimmer_factor = 0.7 + math.sin(led_phases[led]) * 0.5

                    # Apply shimmer factor to create unique color for each LED
                    shimmer_color = tuple(
                        max(0, min(255, int(c * shimmer_factor))) for c in color
                    )

                    # Update LED with its unique color
                    self.led_strip.set_led_color(led, *shimmer_color)

                    # Update phase for this LED
                    led_phases[led] += 0.3 * led_speeds[led]

                # Update entire strip at once
                self.led_strip.update_strip()

                # Wait before next update
                time.sleep(speed)

        except Exception as e:
            logger.error(f"Error in shimmer effect: {str(e)}")
            self._shimmer_active = False
