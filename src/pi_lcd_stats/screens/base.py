"""Base screen class with common drawing helpers."""

from collections import deque

from PIL import Image, ImageDraw, ImageFont

WIDTH = 128
HEIGHT = 128
BG_COLOR = (26, 26, 46)  # #1a1a2e
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD_PATH if bold else FONT_PATH
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


FONT_SM = _load_font(10)
FONT_MD = _load_font(11)
FONT_LG = _load_font(12, bold=True)
FONT_HEADER = _load_font(11, bold=True)
FONT_XS = _load_font(9)


class History:
    """Fixed-size ring buffer for sparkline data."""

    def __init__(self, maxlen: int = 60) -> None:
        self._data: deque[float] = deque(maxlen=maxlen)

    def push(self, value: float) -> None:
        self._data.append(value)

    @property
    def values(self) -> list[float]:
        return list(self._data)

    def __len__(self) -> int:
        return len(self._data)


class BaseScreen:
    """Base class for stat screens."""

    title: str = ""
    header_color: tuple[int, int, int] = (65, 105, 225)
    page_count: int = 1

    def render(
        self,
        screen_index: int,
        total_screens: int,
        page: int = 0,
    ) -> Image.Image:
        """Render the screen and return a PIL Image."""
        img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
        draw = ImageDraw.Draw(img)

        # Title bar
        draw.rectangle([(0, 0), (WIDTH, 14)], fill=self.header_color)
        tw = draw.textlength(self.title, font=FONT_HEADER)
        tx = (WIDTH - tw) // 2
        draw.text((tx, 1), self.title, fill=(255, 255, 255), font=FONT_HEADER)

        # Draw screen content for the current page
        self.draw(draw, page)

        # Screen indicator dots (bottom center)
        self._draw_dots(draw, screen_index, total_screens)

        # Page indicator pips (right edge)
        if self.page_count > 1:
            self._draw_page_pips(draw, page, self.page_count)

        return img

    def draw(self, draw: ImageDraw.ImageDraw, page: int = 0) -> None:
        """Override to draw screen content. Content area starts at y=18."""
        raise NotImplementedError

    @staticmethod
    def draw_label_value(
        draw: ImageDraw.ImageDraw,
        y: int,
        label: str,
        value: str,
        label_color: tuple[int, int, int] = (150, 150, 170),
        value_color: tuple[int, int, int] = (255, 255, 255),
    ) -> None:
        """Draw a label: value pair."""
        draw.text((4, y), label, fill=label_color, font=FONT_SM)
        draw.text(
            (4 + draw.textlength(label, font=FONT_SM) + 3, y),
            value,
            fill=value_color,
            font=FONT_SM,
        )

    @staticmethod
    def draw_progress_bar(
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        width: int,
        height: int,
        percent: float,
        fg_color: tuple[int, int, int] = (0, 200, 120),
        bg_color: tuple[int, int, int] = (50, 50, 70),
    ) -> None:
        """Draw a progress bar with rounded ends."""
        r = height // 2
        draw.rounded_rectangle(
            [(x, y), (x + width, y + height)], radius=r, fill=bg_color
        )
        fill_w = max(0, int(width * min(percent, 100) / 100))
        if fill_w > 0:
            draw.rounded_rectangle(
                [(x, y), (x + fill_w, y + height)], radius=r, fill=fg_color
            )

    @staticmethod
    def draw_sparkline(
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        width: int,
        height: int,
        values: list[float],
        min_val: float = 0,
        max_val: float = 100,
        line_color: tuple[int, int, int] = (0, 200, 120),
        bg_color: tuple[int, int, int] = (40, 40, 60),
    ) -> None:
        """Draw a sparkline chart."""
        # Background
        draw.rectangle([(x, y), (x + width, y + height)], fill=bg_color)

        if len(values) < 2:
            return

        val_range = max_val - min_val
        if val_range == 0:
            val_range = 1

        points = []
        n = len(values)
        for i, v in enumerate(values):
            px = x + int(i * width / (n - 1))
            clamped = max(min_val, min(v, max_val))
            py = y + height - int((clamped - min_val) / val_range * height)
            points.append((px, py))

        # Draw line segments
        for i in range(len(points) - 1):
            draw.line([points[i], points[i + 1]], fill=line_color, width=1)

    @staticmethod
    def _draw_dots(draw: ImageDraw.ImageDraw, current: int, total: int) -> None:
        """Draw screen indicator dots at the bottom center."""
        dot_r = 2
        spacing = 10
        total_w = total * (dot_r * 2) + (total - 1) * (spacing - dot_r * 2)
        start_x = (WIDTH - total_w) // 2
        y = HEIGHT - 6

        for i in range(total):
            cx = start_x + i * spacing + dot_r
            color = (255, 255, 255) if i == current else (80, 80, 100)
            draw.ellipse([(cx - dot_r, y - dot_r), (cx + dot_r, y + dot_r)], fill=color)

    @staticmethod
    def _draw_page_pips(draw: ImageDraw.ImageDraw, current: int, total: int) -> None:
        """Draw page indicator pips on the right edge."""
        pip_h = 3
        spacing = 7
        total_h = total * pip_h + (total - 1) * (spacing - pip_h)
        start_y = (HEIGHT - total_h) // 2
        x = WIDTH - 5

        for i in range(total):
            cy = start_y + i * spacing
            color = (255, 255, 255) if i == current else (60, 60, 80)
            draw.rounded_rectangle([(x, cy), (x + 3, cy + pip_h)], radius=1, fill=color)

    @staticmethod
    def color_for_percent(percent: float) -> tuple[int, int, int]:
        """Return green/yellow/red based on percentage."""
        if percent < 50:
            return (0, 200, 120)
        if percent < 80:
            return (255, 200, 0)
        return (255, 60, 60)

    @staticmethod
    def temp_color(temp: float) -> tuple[int, int, int]:
        """Return color based on temperature."""
        if temp < 50:
            return (0, 200, 120)
        if temp < 70:
            return (255, 200, 0)
        return (255, 60, 60)
