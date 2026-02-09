"""Screen 2: Network information (3 pages)."""

import socket
import subprocess
import time as _time

import psutil
from PIL import ImageDraw

from .base import BaseScreen, FONT_SM

# Set True to hide real network details (for demo videos)
DEMO_MODE = False

_DEMO = {
    "hostname": "raspberrypi",
    "ip": "10.0.1.42",
    "ssid": "MyHomeWiFi",
    "signal": "-52 dBm",
    "mac": "b8:27:eb:a1:b2:c3",
    "gateway": "10.0.1.1",
    "dns": "1.1.1.1",
    "channel": "2437 MHz",
    "bitrate": "72.2 MBit/s",
    "quality": "48",
}


class NetworkScreen(BaseScreen):
    title = "NETWORK"
    header_color = (0, 160, 100)  # Green
    page_count = 3

    def __init__(self) -> None:
        self._prev_io: tuple[int, int] | None = None
        self._prev_time: float = 0
        self._tx_rate: float = 0
        self._rx_rate: float = 0

    def _get_ip(self) -> str:
        if DEMO_MODE:
            return _DEMO["ip"]
        addrs = psutil.net_if_addrs()
        for iface in ("wlan0", "eth0"):
            if iface in addrs:
                for addr in addrs[iface]:
                    if addr.family == socket.AF_INET:
                        return addr.address
        return "No IP"

    def _get_mac(self) -> str:
        if DEMO_MODE:
            return _DEMO["mac"]
        addrs = psutil.net_if_addrs()
        if "wlan0" in addrs:
            for addr in addrs["wlan0"]:
                if addr.family == psutil.AF_LINK:
                    return addr.address
        return "N/A"

    def _get_ssid(self) -> str:
        if DEMO_MODE:
            return _DEMO["ssid"]
        try:
            return (
                subprocess.check_output(
                    ["/usr/sbin/iwgetid", "-r"], text=True, timeout=2
                ).strip()
                or "N/A"
            )
        except (subprocess.SubprocessError, FileNotFoundError):
            return "N/A"

    def _get_signal(self) -> str:
        if DEMO_MODE:
            return _DEMO["signal"]
        try:
            out = subprocess.check_output(
                ["/usr/sbin/iwconfig", "wlan0"],
                text=True,
                timeout=2,
                stderr=subprocess.DEVNULL,
            )
            for line in out.splitlines():
                if "Signal level" in line:
                    part = line.split("Signal level=")[1].split()[0]
                    return f"{part} dBm"
        except (subprocess.SubprocessError, FileNotFoundError, IndexError):
            pass
        return "N/A"

    def _get_wifi_details(self) -> dict[str, str]:
        """Parse iw for channel, bitrate, link quality."""
        if DEMO_MODE:
            return {
                "channel": _DEMO["channel"],
                "bitrate": _DEMO["bitrate"],
                "quality": _DEMO["quality"],
            }
        info: dict[str, str] = {
            "channel": "N/A",
            "bitrate": "N/A",
            "quality": "N/A",
        }
        try:
            out = subprocess.check_output(
                ["iw", "dev", "wlan0", "link"],
                text=True,
                timeout=2,
                stderr=subprocess.DEVNULL,
            )
            for line in out.splitlines():
                line = line.strip()
                if line.startswith("freq:"):
                    info["channel"] = line.split("freq:")[1].strip() + " MHz"
                elif "tx bitrate:" in line:
                    info["bitrate"] = line.split("tx bitrate:")[1].strip()
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

        # Link quality from /proc/net/wireless
        try:
            with open("/proc/net/wireless") as f:
                for line in f:
                    if "wlan0" in line:
                        parts = line.split()
                        info["quality"] = parts[2].rstrip(".")
                        break
        except OSError:
            pass

        return info

    def _get_gateway(self) -> str:
        if DEMO_MODE:
            return _DEMO["gateway"]
        try:
            out = subprocess.check_output(
                ["ip", "route", "show", "default"],
                text=True,
                timeout=2,
            )
            # "default via 192.168.0.1 dev wlan0 ..."
            parts = out.strip().split()
            if len(parts) >= 3 and parts[0] == "default":
                return parts[2]
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
        return "N/A"

    def _get_dns(self) -> str:
        if DEMO_MODE:
            return _DEMO["dns"]
        try:
            with open("/etc/resolv.conf") as f:
                for line in f:
                    if line.startswith("nameserver"):
                        return line.split()[1]
        except (OSError, IndexError):
            pass
        return "N/A"

    def _update_rates(self) -> None:
        """Compute TX/RX rates in KB/s."""
        try:
            io = psutil.net_io_counters(pernic=True).get("wlan0")
            if io is None:
                return
        except (AttributeError, KeyError):
            return

        now = _time.monotonic()
        if self._prev_io is not None and (now - self._prev_time) > 0:
            dt = now - self._prev_time
            self._tx_rate = (io.bytes_sent - self._prev_io[0]) / dt / 1024
            self._rx_rate = (io.bytes_recv - self._prev_io[1]) / dt / 1024
        self._prev_io = (io.bytes_sent, io.bytes_recv)
        self._prev_time = now

    def draw(self, draw: ImageDraw.ImageDraw, page: int = 0) -> None:
        if page == 0:
            self._draw_identity(draw)
        elif page == 1:
            self._draw_traffic(draw)
        else:
            self._draw_wifi_detail(draw)

    def _draw_identity(self, draw: ImageDraw.ImageDraw) -> None:
        """Page 1: Hostname, IP, SSID, signal, MAC."""
        y = 20

        hostname = _DEMO["hostname"] if DEMO_MODE else socket.gethostname()
        self.draw_label_value(draw, y, "HOST:", hostname, value_color=(180, 220, 255))
        y += 14

        ip = self._get_ip()
        self.draw_label_value(draw, y, "IP:", ip, value_color=(0, 230, 180))
        y += 14

        ssid = self._get_ssid()
        self.draw_label_value(draw, y, "SSID:", ssid, value_color=(255, 220, 100))
        y += 14

        signal = self._get_signal()
        self.draw_label_value(draw, y, "SIG:", signal, value_color=(100, 200, 255))
        y += 14

        mac = self._get_mac()
        draw.text((4, y), "MAC:", fill=(150, 150, 170), font=FONT_SM)
        y += 12
        draw.text((4, y), mac, fill=(200, 200, 220), font=FONT_SM)

    def _draw_traffic(self, draw: ImageDraw.ImageDraw) -> None:
        """Page 2: TX/RX rates, errors, connections."""
        self._update_rates()
        y = 18

        draw.text(
            (4, y),
            f"TX: {self._tx_rate:>7.1f} KB/s",
            fill=(100, 220, 180),
            font=FONT_SM,
        )
        y += 14
        draw.text(
            (4, y),
            f"RX: {self._rx_rate:>7.1f} KB/s",
            fill=(100, 200, 255),
            font=FONT_SM,
        )
        y += 16

        # Errors / drops
        try:
            io = psutil.net_io_counters()
            errs = io.errin + io.errout
            drops = io.dropin + io.dropout
        except AttributeError:
            errs = drops = 0

        err_color = (255, 60, 60) if errs > 0 else (0, 200, 120)
        drop_color = (255, 60, 60) if drops > 0 else (0, 200, 120)
        self.draw_label_value(draw, y, "ERRORS:", str(errs), value_color=err_color)
        y += 13
        self.draw_label_value(draw, y, "DROPS:", str(drops), value_color=drop_color)
        y += 16

        # Connection count
        try:
            conns = len(psutil.net_connections(kind="inet"))
        except (psutil.AccessDenied, OSError):
            conns = 0
        self.draw_label_value(
            draw, y, "CONNS:", str(conns), value_color=(180, 220, 255)
        )

    def _draw_wifi_detail(self, draw: ImageDraw.ImageDraw) -> None:
        """Page 3: Wi-Fi channel, bitrate, link quality, gateway, DNS."""
        y = 18

        details = self._get_wifi_details()

        self.draw_label_value(
            draw, y, "FREQ:", details["channel"], value_color=(100, 200, 255)
        )
        y += 13

        self.draw_label_value(
            draw, y, "RATE:", details["bitrate"], value_color=(100, 200, 255)
        )
        y += 13

        self.draw_label_value(
            draw, y, "QUAL:", details["quality"], value_color=(180, 220, 255)
        )
        y += 16

        gw = self._get_gateway()
        self.draw_label_value(draw, y, "GW:", gw, value_color=(0, 230, 180))
        y += 13

        dns = self._get_dns()
        self.draw_label_value(draw, y, "DNS:", dns, value_color=(0, 230, 180))
