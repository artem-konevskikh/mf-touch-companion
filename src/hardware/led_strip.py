import asyncio
import time
import random
import math
from pi5neo import Pi5Neo


class LedStrip:
    def __init__(self, device, num_leds, frequency):
        self.neo = Pi5Neo(device, num_leds, frequency)
        self.current_color = (0, 0, 0)  # Default color is off
        self.steps = 100  # Default steps for transitions
        self._shimmer_active = False

    async def change_color(self, color, steps=None):
        """Fades LED strip from current color to new color (asynchronously)

        Args:
            color (tuple): Target color (R, G, B)
            steps (int, optional): Number of steps for the fade. Uses self.steps if None.
        """
        self._shimmer_active = False  # Stop any active shimmer

        if steps is None:
            steps = self.steps
        else:
            self.steps = steps

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
            await asyncio.sleep(0.01)  # Use asyncio.sleep

        self.current_color = color

    def shimmer(self, color, speed=0.1):
        """Creates a continuous shimmering effect with the given color

        Args:
            color (tuple): Base color (R, G, B)
            speed (float, optional): Speed of the shimmer effect. Defaults to 0.1.
        """
        self._shimmer_active = True
        self.current_color = color

        # Initialize each LED with a different phase to create more natural twinkling
        led_phases = [random.uniform(0, 2 * math.pi) for _ in range(self.neo.num_leds)]
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

                # Update the phase for this LED - increase the speed for more visible changes
                led_phases[led] += 0.3 * led_speeds[led]

            # Update the entire strip at once
            self.neo.update_strip()
            time.sleep(speed)

    def set_intensity(self, intensity, color=None):
        """Sets the intensity/brightness of the LED strip and applies it to a color

        Args:
            intensity (float): Value between 0.0 (off) and 1.0 (full brightness)
            color (tuple, optional): Color to apply intensity to. If None, uses current color.
        """
        self.intensity = max(0.0, min(1.0, intensity))
        color_to_scale = color if color is not None else self.current_color
        scaled_color = tuple(int(c * self.intensity) for c in color_to_scale)

        for led in range(self.neo.num_leds):
            self.neo.set_led_color(led, *scaled_color)
        self.neo.update_strip()
        self.current_color = scaled_color
        return scaled_color

    def clear(self):
        """Clears the LED strip"""
        self._shimmer_active = False
        self.neo.fill_strip(0, 0, 0)
        self.neo.update_strip()
        self.current_color = (0, 0, 0)
