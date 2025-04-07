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

    def change_color(self, color, steps=None):
        """Fades LED strip from current color to new color

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
            time.sleep(0.01)

        self.current_color = color

    def shimmer(self, color, speed=0.1):
        """Creates a continuous shimmering effect with the given color

        Args:
            color (tuple): Base color (R, G, B)
            speed (float, optional): Speed of the shimmer effect. Defaults to 0.1.
        """
        self._shimmer_active = True
        self.current_color = color

        # Use a single phase for all LEDs to create a synchronized wave effect
        phase = 0.0
        try:
            while self._shimmer_active:
                # Calculate the base shimmer factor for this cycle
                base_shimmer = 0.85 + (math.sin(phase) * 0.15)  # Range: 0.7 to 1.0

                # Apply the shimmer effect to all LEDs
                for led in range(self.neo.num_leds):
                    # Add a slight position-based phase offset for a wave-like effect
                    led_offset = (led / self.neo.num_leds) * math.pi * 0.5
                    shimmer_factor = 0.85 + (math.sin(phase + led_offset) * 0.15)

                    # Apply the shimmer factor to create the color
                    shimmer_color = tuple(
                        max(0, min(255, int(c * shimmer_factor))) for c in color
                    )

                    # Update the LED
                    self.neo.set_led_color(led, *shimmer_color)

                # Update the entire strip at once
                self.neo.update_strip()

                # Increment the phase for the next cycle
                phase += 0.1
                
                # Check if shimmer is still active before sleeping
                if not self._shimmer_active:
                    break
                    
                time.sleep(speed)

        except Exception as e:
            print(f"Error in shimmer effect: {e}")
        finally:
            # Ensure strip returns to solid color if shimmer is stopped
            if not self._shimmer_active:
                try:
                    self.change_color(color, steps=1)
                except Exception as e:
                    print(f"Error restoring color after shimmer: {e}")
            
            # Ensure flag is reset even if an exception occurred
            self._shimmer_active = False

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
        """Clears the LED strip and ensures all effects are stopped"""
        # Stop any active shimmer effect
        self._shimmer_active = False
        
        # Give more time for shimmer thread to stop
        time.sleep(0.2)
        
        # Turn off all LEDs
        self.neo.fill_strip(0, 0, 0)
        self.neo.update_strip()
        self.current_color = (0, 0, 0)
