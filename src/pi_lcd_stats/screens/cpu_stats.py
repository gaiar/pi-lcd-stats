"""Screen 1: CPU temperature, voltage, frequency, usage (3 pages)."""

import subprocess

import psutil
from PIL import ImageDraw

from .base import BaseScreen, FONT_LG, FONT_SM, FONT_XS, History

# Throttle flag bitmask (vcgencmd get_throttled)
_THROTTLE_FLAGS = {
    0: ("Under-voltage", (255, 60, 60)),
    1: ("Freq capped", (255, 200, 0)),
    2: ("Throttled", (255, 100, 50)),
    3: ("Soft temp limit", (255, 150, 0)),
    16: ("Under-volt (boot)", (180, 80, 80)),
    17: ("Freq cap (boot)", (180, 160, 60)),
    18: ("Throttled (boot)", (180, 100, 70)),
    19: ("Soft limit (boot)", (180, 130, 60)),
}


class CpuStatsScreen(BaseScreen):
    title = "CPU STATS"
    header_color = (65, 105, 225)  # Royal blue
    page_count = 3

    def __init__(self) -> None:
        self._temp_history = History(maxlen=60)
        self._cpu_history = History(maxlen=60)

    def _read_vcgencmd(self, arg: str) -> str:
        try:
            return subprocess.check_output(
                ["vcgencmd", arg], text=True, timeout=2
            ).strip()
        except (subprocess.SubprocessError, FileNotFoundError):
            return ""

    def _get_temp(self) -> float:
        raw = self._read_vcgencmd("measure_temp")
        try:
            return float(raw.split("=")[1].replace("'C", ""))
        except (IndexError, ValueError):
            return 0.0

    def _get_voltage(self) -> str:
        raw = self._read_vcgencmd("measure_volts")
        try:
            return raw.split("=")[1]
        except IndexError:
            return "N/A"

    def _get_freq(self) -> int:
        """Return CPU frequency in MHz."""
        try:
            with open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq") as f:
                return int(f.read().strip()) // 1000
        except (OSError, ValueError):
            return 0

    def _get_throttled(self) -> int:
        """Return throttle bitmask from vcgencmd."""
        raw = self._read_vcgencmd("get_throttled")
        # "throttled=0x0"
        try:
            return int(raw.split("=")[1], 16)
        except (IndexError, ValueError):
            return -1

    def _get_governor(self) -> str:
        try:
            with open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor") as f:
                return f.read().strip()
        except OSError:
            return "N/A"

    def draw(self, draw: ImageDraw.ImageDraw, page: int = 0) -> None:
        if page == 0:
            self._draw_stats(draw)
        elif page == 1:
            self._draw_throttle(draw)
        else:
            self._draw_history(draw)

    def _draw_stats(self, draw: ImageDraw.ImageDraw) -> None:
        """Page 1: Temperature, voltage, frequency, usage."""
        y = 18

        temp = self._get_temp()
        self._temp_history.push(temp)
        tc = self.temp_color(temp)
        draw.text((4, y), "TEMP", fill=(150, 150, 170), font=FONT_SM)
        draw.text((50, y), f"{temp:.1f}\u00b0C", fill=tc, font=FONT_LG)
        y += 14
        self.draw_progress_bar(draw, 4, y, 118, 6, temp, fg_color=tc)
        y += 12

        voltage = self._get_voltage()
        self.draw_label_value(draw, y, "VOLT:", voltage, value_color=(100, 180, 255))
        y += 14

        freq = self._get_freq()
        self.draw_label_value(
            draw, y, "FREQ:", f"{freq} MHz", value_color=(100, 180, 255)
        )
        y += 14

        usage = psutil.cpu_percent(interval=0)
        self._cpu_history.push(usage)
        uc = self.color_for_percent(usage)
        draw.text((4, y), "CPU", fill=(150, 150, 170), font=FONT_SM)
        draw.text((88, y), f"{usage:.0f}%", fill=uc, font=FONT_SM)
        y += 12
        self.draw_progress_bar(draw, 4, y, 118, 6, usage, fg_color=uc)

    def _draw_throttle(self, draw: ImageDraw.ImageDraw) -> None:
        """Page 2: Throttle status flags."""
        y = 18

        throttled = self._get_throttled()
        if throttled < 0:
            draw.text((4, y), "Cannot read", fill=(255, 60, 60), font=FONT_SM)
            draw.text((4, y + 14), "throttle status", fill=(255, 60, 60), font=FONT_SM)
            return

        if throttled == 0:
            draw.text((4, y), "ALL CLEAR", fill=(0, 200, 120), font=FONT_LG)
            y += 16
            draw.text(
                (4, y), "No throttling detected", fill=(150, 150, 170), font=FONT_SM
            )
            y += 18
        else:
            # Current flags (bits 0-3)
            draw.text((4, y), "CURRENT", fill=(255, 200, 100), font=FONT_XS)
            y += 11
            has_current = False
            for bit in range(4):
                if throttled & (1 << bit):
                    label, color = _THROTTLE_FLAGS[bit]
                    draw.text((8, y), f"\u2022 {label}", fill=color, font=FONT_XS)
                    y += 10
                    has_current = True
            if not has_current:
                draw.text((8, y), "None", fill=(0, 200, 120), font=FONT_XS)
                y += 10

            y += 2
            draw.text((4, y), "SINCE BOOT", fill=(180, 160, 120), font=FONT_XS)
            y += 11
            has_boot = False
            for bit in range(16, 20):
                if throttled & (1 << bit):
                    label, color = _THROTTLE_FLAGS[bit]
                    draw.text((8, y), f"\u2022 {label}", fill=color, font=FONT_XS)
                    y += 10
                    has_boot = True
            if not has_boot:
                draw.text((8, y), "None", fill=(0, 200, 120), font=FONT_XS)

        # Governor at bottom
        gov = self._get_governor()
        self.draw_label_value(draw, 108, "GOV:", gov, value_color=(100, 180, 255))

    def _draw_history(self, draw: ImageDraw.ImageDraw) -> None:
        """Page 3: Temperature and CPU sparkline graphs."""
        y = 18

        # Temperature sparkline
        temp = self._get_temp()
        self._temp_history.push(temp)
        tc = self.temp_color(temp)
        draw.text((4, y), "TEMP", fill=(150, 150, 170), font=FONT_XS)
        draw.text((80, y), f"{temp:.1f}\u00b0C", fill=tc, font=FONT_SM)
        y += 11
        self.draw_sparkline(
            draw,
            4,
            y,
            118,
            30,
            self._temp_history.values,
            min_val=25,
            max_val=85,
            line_color=tc,
        )
        y += 34

        # CPU usage sparkline
        usage = psutil.cpu_percent(interval=0)
        self._cpu_history.push(usage)
        uc = self.color_for_percent(usage)
        draw.text((4, y), "CPU", fill=(150, 150, 170), font=FONT_XS)
        draw.text((80, y), f"{usage:.0f}%", fill=uc, font=FONT_SM)
        y += 11
        self.draw_sparkline(
            draw,
            4,
            y,
            118,
            30,
            self._cpu_history.values,
            min_val=0,
            max_val=100,
            line_color=uc,
        )
