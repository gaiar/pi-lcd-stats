"""ST7735S SPI display driver for Waveshare 1.44inch LCD HAT."""

import os
import time

import lgpio
import numpy as np
import spidev
from PIL import Image


class DisplayNotFoundError(Exception):
    """Raised when the LCD HAT hardware is not detected."""


# Pin definitions
DC_PIN = 25
RST_PIN = 27
BL_PIN = 24

# Display dimensions
WIDTH = 128
HEIGHT = 128

# ST7735S offsets (132x162 panel, 128x128 visible)
X_OFFSET = 1
Y_OFFSET = 2

# ST7735S commands
_SWRESET = 0x01
_SLPOUT = 0x11
_FRMCTR1 = 0xB1
_FRMCTR2 = 0xB2
_FRMCTR3 = 0xB3
_INVCTR = 0xB4
_PWCTR1 = 0xC0
_PWCTR2 = 0xC1
_PWCTR3 = 0xC2
_PWCTR4 = 0xC3
_PWCTR5 = 0xC4
_VMCTR1 = 0xC5
_INVOFF = 0x20
_MADCTL = 0x36
_COLMOD = 0x3A
_CASET = 0x2A
_RASET = 0x2B
_RAMWR = 0x2C
_GMCTRP1 = 0xE0
_GMCTRN1 = 0xE1
_NORON = 0x13
_DISPON = 0x29


class Display:
    """Drive the ST7735S 128x128 LCD via SPI."""

    def __init__(self) -> None:
        if not os.path.exists("/dev/spidev0.0"):
            raise DisplayNotFoundError("SPI device /dev/spidev0.0 not found")

        try:
            self._gpio = lgpio.gpiochip_open(0)
        except lgpio.error as e:
            raise DisplayNotFoundError(f"Cannot open GPIO: {e}") from e

        lgpio.gpio_claim_output(self._gpio, DC_PIN)
        lgpio.gpio_claim_output(self._gpio, RST_PIN)

        try:
            self._spi = spidev.SpiDev()
            self._spi.open(0, 0)
        except OSError as e:
            lgpio.gpiochip_close(self._gpio)
            raise DisplayNotFoundError(f"Cannot open SPI: {e}") from e

        self._spi.max_speed_hz = 16_000_000
        self._spi.mode = 0

        self._init_display()

        lgpio.gpio_claim_output(self._gpio, BL_PIN)
        self._backlight = True
        lgpio.gpio_write(self._gpio, BL_PIN, 1)

    def toggle_backlight(self) -> bool:
        """Toggle backlight on/off. Return new state."""
        self._backlight = not self._backlight
        lgpio.gpio_write(self._gpio, BL_PIN, 1 if self._backlight else 0)
        return self._backlight

    def _cmd(self, cmd: int, data: bytes | None = None) -> None:
        """Send command, optionally followed by data bytes."""
        lgpio.gpio_write(self._gpio, DC_PIN, 0)
        self._spi.writebytes([cmd])
        if data:
            lgpio.gpio_write(self._gpio, DC_PIN, 1)
            self._spi.writebytes(list(data))

    def _data(self, data: bytes) -> None:
        """Send data bytes."""
        lgpio.gpio_write(self._gpio, DC_PIN, 1)
        self._spi.writebytes(list(data))

    def _reset(self) -> None:
        lgpio.gpio_write(self._gpio, RST_PIN, 1)
        time.sleep(0.01)
        lgpio.gpio_write(self._gpio, RST_PIN, 0)
        time.sleep(0.01)
        lgpio.gpio_write(self._gpio, RST_PIN, 1)
        time.sleep(0.15)

    def _init_display(self) -> None:
        self._reset()

        self._cmd(_SWRESET)
        time.sleep(0.15)

        self._cmd(_SLPOUT)
        time.sleep(0.5)

        # Frame rate control
        self._cmd(_FRMCTR1, b"\x01\x2c\x2d")
        self._cmd(_FRMCTR2, b"\x01\x2c\x2d")
        self._cmd(_FRMCTR3, b"\x01\x2c\x2d\x01\x2c\x2d")

        self._cmd(_INVCTR, b"\x07")

        # Power control
        self._cmd(_PWCTR1, b"\xa2\x02\x84")
        self._cmd(_PWCTR2, b"\xc5")
        self._cmd(_PWCTR3, b"\x0a\x00")
        self._cmd(_PWCTR4, b"\x8a\x2a")
        self._cmd(_PWCTR5, b"\x8a\xee")

        self._cmd(_VMCTR1, b"\x0e")

        self._cmd(_INVOFF)

        # MADCTL: Row/Column exchange, BGR color order
        self._cmd(_MADCTL, b"\x60")

        # 16-bit color (RGB565)
        self._cmd(_COLMOD, b"\x05")

        # Gamma
        self._cmd(
            _GMCTRP1,
            b"\x02\x1c\x07\x12\x37\x32\x29\x2d\x29\x25\x2b\x39\x00\x01\x03\x10",
        )
        self._cmd(
            _GMCTRN1,
            b"\x03\x1d\x07\x06\x2e\x2c\x29\x2d\x2e\x2e\x37\x3f\x00\x00\x02\x10",
        )

        self._cmd(_NORON)
        time.sleep(0.01)

        self._cmd(_DISPON)
        time.sleep(0.1)

    def _set_window(self, x0: int, y0: int, x1: int, y1: int) -> None:
        """Set the drawing window."""
        self._cmd(
            _CASET,
            bytes([0x00, x0 + X_OFFSET, 0x00, x1 + X_OFFSET]),
        )
        self._cmd(
            _RASET,
            bytes([0x00, y0 + Y_OFFSET, 0x00, y1 + Y_OFFSET]),
        )
        self._cmd(_RAMWR)

    def show(self, image: Image.Image) -> None:
        """Display a PIL Image on the LCD."""
        if image.size != (WIDTH, HEIGHT):
            image = image.resize((WIDTH, HEIGHT))

        # Vectorized RGB888→RGB565 conversion via numpy (75x faster than Python loop)
        arr = np.frombuffer(image.convert("RGB").tobytes(), dtype=np.uint8).reshape(
            -1, 3
        )
        r = arr[:, 0].astype(np.uint16)
        g = arr[:, 1].astype(np.uint16)
        b = arr[:, 2].astype(np.uint16)
        rgb565 = ((b & 0xF8) << 8) | ((g & 0xFC) << 3) | (r >> 3)
        buf = np.empty(rgb565.size * 2, dtype=np.uint8)
        buf[0::2] = (rgb565 >> 8).astype(np.uint8)
        buf[1::2] = (rgb565 & 0xFF).astype(np.uint8)

        self._set_window(0, 0, WIDTH - 1, HEIGHT - 1)
        lgpio.gpio_write(self._gpio, DC_PIN, 1)
        self._spi.writebytes2(buf.tobytes())

    def close(self) -> None:
        lgpio.gpio_write(self._gpio, BL_PIN, 0)
        self._spi.close()
        lgpio.gpiochip_close(self._gpio)
