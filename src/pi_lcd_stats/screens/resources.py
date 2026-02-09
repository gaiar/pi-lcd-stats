"""Screen 3: System resources (3 pages)."""

import os
import time as _time

import psutil
from PIL import ImageDraw

from .base import BaseScreen, FONT_SM, FONT_XS


class ResourcesScreen(BaseScreen):
    title = "RESOURCES"
    header_color = (220, 120, 0)  # Orange
    page_count = 3

    def __init__(self) -> None:
        self._prev_disk_io: tuple[int, int] | None = None
        self._prev_disk_time: float = 0
        self._read_rate: float = 0
        self._write_rate: float = 0

    def _get_uptime(self) -> str:
        try:
            with open("/proc/uptime") as f:
                seconds = float(f.read().split()[0])
        except (OSError, ValueError):
            return "N/A"
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        mins = int((seconds % 3600) // 60)
        if days > 0:
            return f"{days}d {hours}h {mins}m"
        return f"{hours}h {mins}m"

    def _get_swap(self) -> tuple[float, int, int]:
        """Return (percent, used_mb, total_mb)."""
        swap = psutil.swap_memory()
        return swap.percent, swap.used // (1024 * 1024), swap.total // (1024 * 1024)

    def _get_gpu_arm_mem(self) -> tuple[str, str]:
        """Return GPU and ARM memory allocation from vcgencmd."""
        import subprocess

        gpu = arm = "N/A"
        try:
            raw = subprocess.check_output(
                ["vcgencmd", "get_mem", "gpu"], text=True, timeout=2
            ).strip()
            gpu = raw.split("=")[1]
        except (subprocess.SubprocessError, FileNotFoundError, IndexError):
            pass
        try:
            raw = subprocess.check_output(
                ["vcgencmd", "get_mem", "arm"], text=True, timeout=2
            ).strip()
            arm = raw.split("=")[1]
        except (subprocess.SubprocessError, FileNotFoundError, IndexError):
            pass
        return gpu, arm

    def _get_meminfo_field(self, field: str) -> int:
        """Return a /proc/meminfo field value in KB."""
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith(field):
                        return int(line.split()[1])
        except (OSError, ValueError, IndexError):
            pass
        return 0

    def _update_disk_rates(self) -> None:
        """Compute disk read/write rates in KB/s."""
        try:
            io = psutil.disk_io_counters()
        except (AttributeError, RuntimeError):
            return

        now = _time.monotonic()
        if self._prev_disk_io is not None and (now - self._prev_disk_time) > 0:
            dt = now - self._prev_disk_time
            self._read_rate = (io.read_bytes - self._prev_disk_io[0]) / dt / 1024
            self._write_rate = (io.write_bytes - self._prev_disk_io[1]) / dt / 1024
        self._prev_disk_io = (io.read_bytes, io.write_bytes)
        self._prev_disk_time = now

    def _get_top_procs(self, n: int = 4) -> list[tuple[str, float]]:
        """Return top N processes by CPU percent."""
        procs = []
        for p in psutil.process_iter(["name", "cpu_percent"]):
            try:
                info = p.info
                procs.append((info["name"] or "?", info["cpu_percent"] or 0.0))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        procs.sort(key=lambda x: x[1], reverse=True)
        return procs[:n]

    def draw(self, draw: ImageDraw.ImageDraw, page: int = 0) -> None:
        if page == 0:
            self._draw_overview(draw)
        elif page == 1:
            self._draw_memory(draw)
        else:
            self._draw_processes(draw)

    def _draw_overview(self, draw: ImageDraw.ImageDraw) -> None:
        """Page 1: Load, RAM, SD, processes, uptime."""
        y = 18

        load1, load5, load15 = os.getloadavg()
        self.draw_label_value(
            draw,
            y,
            "LOAD:",
            f"{load1:.1f} {load5:.1f} {load15:.1f}",
            value_color=(180, 200, 255),
        )
        y += 14

        mem = psutil.virtual_memory()
        mem_pct = mem.percent
        used_mb = mem.used // (1024 * 1024)
        total_mb = mem.total // (1024 * 1024)
        mc = self.color_for_percent(mem_pct)
        draw.text((4, y), "RAM", fill=(150, 150, 170), font=FONT_SM)
        draw.text((70, y), f"{used_mb}/{total_mb}M", fill=mc, font=FONT_SM)
        y += 12
        self.draw_progress_bar(draw, 4, y, 118, 6, mem_pct, fg_color=mc)
        y += 12

        disk = psutil.disk_usage("/")
        disk_pct = disk.percent
        used_gb = disk.used / (1024**3)
        total_gb = disk.total / (1024**3)
        dc = self.color_for_percent(disk_pct)
        draw.text((4, y), "SD", fill=(150, 150, 170), font=FONT_SM)
        draw.text((55, y), f"{used_gb:.1f}/{total_gb:.1f}G", fill=dc, font=FONT_SM)
        y += 12
        self.draw_progress_bar(draw, 4, y, 118, 6, disk_pct, fg_color=dc)
        y += 12

        procs = len(psutil.pids())
        self.draw_label_value(
            draw, y, "PROCS:", str(procs), value_color=(180, 220, 255)
        )
        y += 14

        uptime = self._get_uptime()
        self.draw_label_value(draw, y, "UP:", uptime, value_color=(100, 255, 200))

    def _draw_memory(self, draw: ImageDraw.ImageDraw) -> None:
        """Page 2: Swap, buffers/cache, GPU/ARM split."""
        y = 18

        # Swap
        swap_pct, swap_used, swap_total = self._get_swap()
        if swap_total > 0:
            sc = self.color_for_percent(swap_pct)
            draw.text((4, y), "SWAP", fill=(150, 150, 170), font=FONT_SM)
            draw.text((60, y), f"{swap_used}/{swap_total}M", fill=sc, font=FONT_SM)
            y += 12
            self.draw_progress_bar(draw, 4, y, 118, 6, swap_pct, fg_color=sc)
            y += 12
        else:
            self.draw_label_value(
                draw, y, "SWAP:", "disabled", value_color=(100, 100, 120)
            )
            y += 14

        # Buffers / Cache
        buffers_kb = self._get_meminfo_field("Buffers:")
        cached_kb = self._get_meminfo_field("Cached:")
        buffers_mb = buffers_kb // 1024
        cached_mb = cached_kb // 1024
        self.draw_label_value(
            draw,
            y,
            "BUF/CACHE:",
            f"{buffers_mb}/{cached_mb}M",
            value_color=(180, 200, 255),
        )
        y += 14

        # Available
        avail_kb = self._get_meminfo_field("MemAvailable:")
        avail_mb = avail_kb // 1024
        self.draw_label_value(
            draw, y, "AVAIL:", f"{avail_mb}M", value_color=(0, 200, 120)
        )
        y += 14

        # Dirty pages
        dirty_kb = self._get_meminfo_field("Dirty:")
        dirty_color = (255, 200, 0) if dirty_kb > 1024 else (0, 200, 120)
        self.draw_label_value(
            draw, y, "DIRTY:", f"{dirty_kb}K", value_color=dirty_color
        )
        y += 16

        # GPU / ARM split
        gpu_mem, arm_mem = self._get_gpu_arm_mem()
        self.draw_label_value(draw, y, "GPU:", gpu_mem, value_color=(180, 160, 255))
        y += 13
        self.draw_label_value(draw, y, "ARM:", arm_mem, value_color=(180, 160, 255))

    def _draw_processes(self, draw: ImageDraw.ImageDraw) -> None:
        """Page 3: Top processes by CPU + disk I/O rates."""
        y = 18

        # Disk I/O
        self._update_disk_rates()
        draw.text((4, y), "DISK I/O", fill=(150, 150, 170), font=FONT_XS)
        y += 11
        draw.text(
            (4, y),
            f"R: {self._read_rate:>6.0f} KB/s",
            fill=(100, 200, 255),
            font=FONT_XS,
        )
        draw.text(
            (68, y),
            f"W: {self._write_rate:>5.0f} KB/s",
            fill=(255, 180, 100),
            font=FONT_XS,
        )
        y += 11

        # iowait
        try:
            iowait = psutil.cpu_times_percent(interval=0).iowait
        except AttributeError:
            iowait = 0
        iow_color = (255, 60, 60) if iowait > 10 else (0, 200, 120)
        self.draw_label_value(
            draw, y, "IOWAIT:", f"{iowait:.1f}%", value_color=iow_color
        )
        y += 14

        # Top processes
        draw.text((4, y), "TOP PROCS", fill=(150, 150, 170), font=FONT_XS)
        y += 11

        top = self._get_top_procs(4)
        for name, cpu in top:
            truncated = name[:14]
            pc = self.color_for_percent(cpu)
            draw.text((4, y), truncated, fill=(200, 200, 220), font=FONT_XS)
            draw.text((95, y), f"{cpu:4.1f}%", fill=pc, font=FONT_XS)
            y += 10
