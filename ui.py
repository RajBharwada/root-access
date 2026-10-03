"""Shared look & feel: palette, fonts, text helpers and the Menu widget."""
import pygame

BG = (8, 12, 10)
PANEL = (14, 24, 19)
BORDER = (40, 120, 70)

# One colour per meaning, used everywhere (also shown on the How to Play page).
COLORS = {
    "out": (120, 255, 150),      # normal output
    "cmd": (240, 245, 240),      # what you typed
    "prompt": (90, 200, 255),    # the prompt  host:/path$
    "error": (255, 105, 105),
    "good": (255, 224, 90),      # success / headings
    "hint": (255, 170, 60),      # hints and tips
    "info": (150, 180, 165),     # system notes
    "select": (35, 85, 150),     # text-selection background
    "bar": (28, 70, 48),         # highlighted menu row
    "term_bg": (5, 9, 7),
    "cursor": (120, 255, 150),
}

FONT_NAMES = ("dejavusansmono,liberationmono,consolas,couriernew,ubuntumono,"
              "notomono,menlo,monaco,freemono")


def make_font(size, bold=False):
    path = pygame.font.match_font(FONT_NAMES, bold=bold)
    if path:
        return pygame.font.Font(path, size)
    return pygame.font.SysFont("monospace", size, bold=bold)


def wrap_text(text, font, max_width):
    """Word-wrap text to a pixel width. Returns a list of lines."""
    lines = []
    for para in str(text).split("\n"):
        cur = ""
        for word in para.split(" "):
            trial = word if not cur else cur + " " + word
            if not cur or font.size(trial)[0] <= max_width:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


def fit(font, text, width):
    """How many leading characters of `text` fit in `width` pixels (min 1)."""
    if not text:
        return 0
    if font.size(text)[0] <= width:
        return len(text)
    lo, hi, best = 1, len(text) - 1, 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if font.size(text[:mid])[0] <= width:
            best, lo = mid, mid + 1
        else:
            hi = mid - 1
    return best


def col_at_x(font, text, x):
    """Character index nearest to pixel offset x."""
    if x <= 0:
        return 0
    prev = 0
    for i in range(1, len(text) + 1):
        w = font.size(text[:i])[0]
        if x < (prev + w) / 2:
            return i - 1
        prev = w
    return len(text)


DEFAULT_FOOTER = "Up/Down: choose    Enter: select    Esc: back"


class Menu:
    """Keyboard + mouse menu. handle_event returns (action, delta) or None.
    delta is 0 for a plain activation, -1/+1 for Left/Right on items with a value."""

    def __init__(self, title, items, subtitle="", title_font="big",
                 title_color="out", footer=DEFAULT_FOOTER):
        self.title, self.items, self.subtitle = title, items, subtitle
        self.title_font, self.title_color, self.footer = title_font, title_color, footer
        self.sel = self._first_enabled()
        self._rects = []

    def _enabled(self, i):
        return self.items[i].get("enabled", True)

    def _first_enabled(self):
        for i in range(len(self.items)):
            if self._enabled(i):
                return i
        return 0

    def move(self, step):
        n = len(self.items)
        for _ in range(n):
            self.sel = (self.sel + step) % n
            if self._enabled(self.sel):
                return

    def _activate(self, delta=0):
        item = self.items[self.sel]
        if self._enabled(self.sel):
            return (item["action"], delta)
        return None

    def _has_value(self):
        return self.items[self.sel].get("value") is not None

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            k = event.key
            if k == pygame.K_UP:
                self.move(-1)
            elif k == pygame.K_DOWN:
                self.move(1)
            elif k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                return self._activate(0)
            elif k == pygame.K_LEFT and self._has_value():
                return self._activate(-1)
            elif k == pygame.K_RIGHT and self._has_value():
                return self._activate(1)
            elif k == pygame.K_ESCAPE:
                return ("__back__", 0)
        elif event.type == pygame.MOUSEMOTION:
            for rect, i in self._rects:
                if rect.collidepoint(event.pos) and self._enabled(i):
                    self.sel = i
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, i in self._rects:
                if rect.collidepoint(event.pos) and self._enabled(i):
                    self.sel = i
                    return self._activate(1 if self._has_value() else 0)
        return None

    def draw(self, surface, fonts, area, boxed=False):
        ui, small = fonts["ui"], fonts["small"]
        width = min(area.width - 40, 620)
        cx = area.centerx
        title_font = fonts[self.title_font]
        for cand in (title_font, fonts["mid"], ui):
            title_font = cand
            if cand.size(self.title)[0] <= area.width - 40:
                break
        title = title_font.render(self.title, True, COLORS[self.title_color])
        sub = wrap_text(self.subtitle, small, width) if self.subtitle else []
        row_h = ui.get_linesize() + 16
        content_h = (title.get_height() + 10
                     + (len(sub) * small.get_linesize() + 14 if sub else 0)
                     + 20 + len(self.items) * row_h)
        top = area.y + max(24, (area.height - content_h) // 2 - (0 if boxed else 20))
        if boxed:
            box = pygame.Rect(cx - width // 2 - 30, top - 24, width + 60, content_h + 48)
            pygame.draw.rect(surface, PANEL, box)
            pygame.draw.rect(surface, BORDER, box, 2)
        y = top
        surface.blit(title, (cx - title.get_width() // 2, y))
        y += title.get_height() + 10
        for line in sub:
            s = small.render(line, True, COLORS["info"])
            surface.blit(s, (cx - s.get_width() // 2, y))
            y += small.get_linesize()
        if sub:
            y += 14
        y += 20
        self._rects = []
        for i, item in enumerate(self.items):
            rect = pygame.Rect(cx - width // 2, y, width, row_h - 6)
            label = item["label"]
            if item.get("value") is not None:
                label = "%s:  %s" % (label, item["value"])
            enabled = self._enabled(i)
            selected = (i == self.sel and enabled)
            if selected:
                pygame.draw.rect(surface, COLORS["bar"], rect)
                pygame.draw.rect(surface, COLORS["out"], rect, 1)
                label = "> " + label
            color = COLORS["cmd"] if selected else (COLORS["out"] if enabled else COLORS["info"])
            text = ui.render(label, True, color)
            surface.blit(text, (cx - text.get_width() // 2,
                                rect.y + (rect.height - text.get_height()) // 2))
            self._rects.append((rect, i))
            y += row_h
        if self.footer:
            f = small.render(self.footer, True, COLORS["info"])
            surface.blit(f, (cx - f.get_width() // 2, area.bottom - 34))