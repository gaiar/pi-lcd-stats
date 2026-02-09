"""Entry point: main loop with screen management and input handling."""

import logging
import signal
import sys
import time

from .display import Display, DisplayNotFoundError
from .input import InputHandler
from .screens import network as _network_mod
from .screens.cpu_stats import CpuStatsScreen
from .screens.network import NetworkScreen
from .screens.resources import ResourcesScreen

log = logging.getLogger("pi-lcd-stats")

SCREENS = [CpuStatsScreen(), NetworkScreen(), ResourcesScreen()]
TOTAL = len(SCREENS)
REFRESH_INTERVAL = 2.0  # seconds between data refresh
POLL_SLEEP = 0.1  # seconds between input polls
DEMO_PAGE_INTERVAL = 4.0  # seconds per page in demo auto-cycle


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(name)s: %(message)s",
    )

    demo_mode = "--demo" in sys.argv
    if demo_mode:
        _network_mod.DEMO_MODE = True
        log.info("Demo mode enabled — auto-cycling with fake network data.")

    try:
        display = Display()
    except DisplayNotFoundError as e:
        log.info("LCD HAT not detected (%s) — exiting.", e)
        sys.exit(0)

    gpio_handle = display._gpio
    inp = InputHandler(gpio_handle)
    log.info("Started — LCD HAT detected.")

    screen_idx = 0
    page_idx = 0
    last_refresh = 0.0
    last_auto_advance = time.monotonic()
    running = True

    def shutdown(_signum: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        while running:
            event = inp.poll()
            if event == "RIGHT":
                screen_idx = (screen_idx + 1) % TOTAL
                page_idx = 0
                last_refresh = 0.0
                last_auto_advance = time.monotonic()
            elif event == "LEFT":
                screen_idx = (screen_idx - 1) % TOTAL
                page_idx = 0
                last_refresh = 0.0
                last_auto_advance = time.monotonic()
            elif event == "DOWN":
                pc = SCREENS[screen_idx].page_count
                page_idx = (page_idx + 1) % pc
                last_refresh = 0.0
                last_auto_advance = time.monotonic()
            elif event == "UP":
                pc = SCREENS[screen_idx].page_count
                page_idx = (page_idx - 1) % pc
                last_refresh = 0.0
                last_auto_advance = time.monotonic()
            elif event == "KEY1":
                screen_idx = 0
                page_idx = 0
                last_refresh = 0.0
                last_auto_advance = time.monotonic()
            elif event == "KEY2":
                screen_idx = 1
                page_idx = 0
                last_refresh = 0.0
                last_auto_advance = time.monotonic()
            elif event == "KEY3":
                screen_idx = 2
                page_idx = 0
                last_refresh = 0.0
                last_auto_advance = time.monotonic()
            elif event == "PRESS":
                state = display.toggle_backlight()
                log.info("Backlight: %s", "on" if state else "off")

            # Demo auto-cycle: advance to next page/screen
            now = time.monotonic()
            if demo_mode and now - last_auto_advance >= DEMO_PAGE_INTERVAL:
                last_auto_advance = now
                pc = SCREENS[screen_idx].page_count
                if page_idx < pc - 1:
                    page_idx += 1
                else:
                    screen_idx = (screen_idx + 1) % TOTAL
                    page_idx = 0
                last_refresh = 0.0

            # Refresh display at interval or on screen/page change
            if now - last_refresh >= REFRESH_INTERVAL:
                last_refresh = now
                screen = SCREENS[screen_idx]
                img = screen.render(screen_idx, TOTAL, page_idx)
                display.show(img)

            time.sleep(POLL_SLEEP)

    finally:
        display.close()


if __name__ == "__main__":
    main()
