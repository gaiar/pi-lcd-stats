"""Button and joystick input handler using lgpio."""

import time

import lgpio

# Pin mapping for Waveshare 1.44" LCD HAT
PINS = {
    "KEY1": 21,
    "KEY2": 20,
    "KEY3": 16,
    "UP": 6,
    "DOWN": 19,
    "LEFT": 5,
    "RIGHT": 26,
    "PRESS": 13,
}

DEBOUNCE_MS = 200


class InputHandler:
    """Read button and joystick events with debouncing."""

    def __init__(self, gpio_handle: int) -> None:
        self._gpio = gpio_handle
        self._last_event_time: dict[str, float] = {}

        for name, pin in PINS.items():
            lgpio.gpio_claim_input(self._gpio, pin, lgpio.SET_PULL_UP)
            self._last_event_time[name] = 0.0

    def poll(self) -> str | None:
        """Return the name of a pressed button, or None."""
        now = time.monotonic()
        for name, pin in PINS.items():
            if lgpio.gpio_read(self._gpio, pin) == 0:
                if (now - self._last_event_time[name]) > (DEBOUNCE_MS / 1000):
                    self._last_event_time[name] = now
                    return name
        return None
