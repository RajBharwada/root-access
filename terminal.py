"""Terminal widget: scrollback, a real line editor (cursor, history, Tab),
mouse text selection and clipboard copy/paste."""
import pygame

import clipboard
from lineedit import LineEditor
from ui import COLORS, col_at_x, fit

PAD = 10
MAX_LINES = 3000


def word_bounds(text, col):
    """Start/end of the non-space run containing column `col`."""
    if not text:
        return 0, 0
    col = min(col, len(text) - 1)
    if text[col].isspace():
        return col, col
    s = col
    while s > 0 and not text[s - 1].isspace():
        s -= 1
    e = col
    while e < len(text) and not text[e].isspace():
        e += 1
    return s, e


class Terminal:
    def __init__(self, rect, font):
        self.rect = pygame.Rect(rect)
        self.editor = LineEditor()
        self.prompt = "$ "
        self.completer = None       # callable(text_before_cursor) -> (new_text, options)
        self.lines = []             # logical lines: (text, style)
        self._rev = 0
        self._wrap_key = None
        self._wrapped_cache = []
        self.scroll = 0
        self.hscroll = 0
        self.sel = None             # ((line, col), (line, col)) over wrapped lines
        self.dragging = False
        self._click = (0, (0, 0), 0)
        self._toast = ("", 0)
        self._blink = 0
        self.set_font(font)

    # ------------------------------------------------------------ layout
    def set_font(self, font):
        self.font = font
        self.line_h = font.get_linesize()
        self.char_w = font.size("M")[0]
        self._invalidate()
        self.scroll = 0
        self.hscroll = 0

    def set_rect(self, rect):
        self.rect = pygame.Rect(rect)
        self._invalidate()

    def _invalidate(self):
        self._rev += 1
        self.sel = None

    @property
    def text_width(self):
        return max(60, self.rect.width - 2 * PAD)

    @property
    def rows(self):
        return max(2, (self.rect.height - 2 * PAD) // self.line_h)

    # ------------------------------------------------------------ output
    def _append(self, text, style):
        self.lines.append((text, style))
        if len(self.lines) > MAX_LINES:
            del self.lines[:len(self.lines) - MAX_LINES]
        self._invalidate()
        self.scroll = 0

    def print(self, text, style="out"):
        for raw in str(text).split("\n"):
            self._append(raw, style)

    def clear(self):
        self.lines = []
        self._invalidate()
        self.scroll = 0

    def toast(self, text):
        self._toast = (text, pygame.time.get_ticks() + 1800)

    def _wrapped(self):
        key = (self._rev, self.text_width)
        if key == self._wrap_key:
            return self._wrapped_cache
        out = []
        for text, style in self.lines:
            if not text:
                out.append(("", style, None))
                continue
            raw, sep, st = text, None, style
            while True:
                n = fit(self.font, raw, self.text_width)
                if n >= len(raw):
                    out.append((raw, st, sep))
                    break
                k = raw.rfind(" ", 0, n + 1)
                if k > n * 0.4:
                    piece, raw, nxt = raw[:k], raw[k + 1:], " "
                else:
                    piece, raw, nxt = raw[:n], raw[n:], ""
                out.append((piece, st, sep))
                sep = nxt
                if isinstance(style, tuple):
                    st = "cmd"
                if not raw:
                    break
        self._wrap_key = key
        self._wrapped_cache = out
        return out

    def _view(self):
        w = self._wrapped()
        visible = self.rows - 1
        self.scroll = max(0, min(self.scroll, max(0, len(w) - visible)))
        end = len(w) - self.scroll
        return max(0, end - visible), end

    # ------------------------------------------------------------ selection
    def _sel_range(self):
        if not self.sel:
            return None, None
        a, b = self.sel
        if a > b:
            a, b = b, a
        if a == b:
            return None, None
        return a, b

    def selected_text(self):
        a, b = self._sel_range()
        if a is None:
            return ""
        w = self._wrapped()
        parts = []
        for i in range(a[0], b[0] + 1):
            if i >= len(w):
                break
            text, _, join = w[i]
            s = a[1] if i == a[0] else 0
            e = b[1] if i == b[0] else len(text)
            if i > a[0]:
                parts.append("\n" if join is None else join)
            parts.append(text[s:e])
        return "".join(parts).rstrip()

    def _hit(self, pos):
        start, end = self._view()
        w = self._wrapped()
        row = max(0, (pos[1] - self.rect.y - PAD) // self.line_h)
        x = pos[0] - self.rect.x - PAD
        if start + row >= end:
            prompt_w = self.font.size(self.prompt)[0]
            text = self.editor.text[self.hscroll:]
            col = col_at_x(self.font, text, x - prompt_w) + self.hscroll
            return ("input", min(col, len(self.editor.text)))
        idx = start + row
        return ("out", idx, col_at_x(self.font, w[idx][0], x))

    # ------------------------------------------------------------ clipboard
    def copy(self):
        text = self.selected_text() or self.editor.text
        if not text.strip():
            self.toast("Select text with the mouse first, then press Ctrl+C")
            return
        ok = clipboard.copy(text)
        self.toast("Copied %d characters" % len(text) if ok
                   else "Copied (usable inside the game)")

    def paste(self):
        text = clipboard.paste()
        if text:
            self._edit()
            self.editor.insert(text, paste=True)
            self.toast("Pasted")
        else:
            self.toast("Clipboard is empty")

    # ------------------------------------------------------------ input
    def _edit(self):
        self.sel = None
        self.scroll = 0
        self._blink = pygame.time.get_ticks()

    def _complete(self):
        if not self.completer:
            return
        ed = self.editor
        before, after = ed.text[:ed.pos], ed.text[ed.pos:]
        new_before, options = self.completer(before)
        self._edit()
        ed.text = new_before + after
        ed.pos = len(new_before)
        if len(options) > 1 and new_before == before:
            self.print("  ".join(options), "info")

    def handle_event(self, event):
        """Feed pygame events here. Returns the submitted line on Enter, else None."""
        t = event.type
        if t == pygame.TEXTINPUT:
            self._edit()
            self.editor.insert(event.text)
        elif t == pygame.KEYDOWN:
            return self._on_key(event)
        elif t == pygame.MOUSEWHEEL:
            if self.rect.collidepoint(pygame.mouse.get_pos()):
                self.scroll = max(0, self.scroll + event.y * 3)
        elif t == pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(event.pos):
            if event.button == 1:
                self._click_left(event.pos)
            elif event.button == 3:
                self.paste()
        elif t == pygame.MOUSEMOTION and self.dragging and self.sel:
            hit = self._hit(event.pos)
            if hit[0] == "out":
                self.sel = (self.sel[0], (hit[1], hit[2]))
            else:
                start, end = self._view()
                if end > 0:
                    last = self._wrapped()[end - 1][0]
                    self.sel = (self.sel[0], (end - 1, len(last)))
        elif t == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.dragging and self.sel and self.sel[0] == self.sel[1]:
                self.sel = None
            self.dragging = False
        return None

    def _click_left(self, pos):
        now = pygame.time.get_ticks()
        last_t, last_pos, count = self._click
        near = abs(pos[0] - last_pos[0]) < 6 and abs(pos[1] - last_pos[1]) < 6
        count = count + 1 if (now - last_t < 400 and near) else 1
        if count > 3:
            count = 1
        self._click = (now, pos, count)
        hit = self._hit(pos)
        if hit[0] == "input":
            self.editor.pos = hit[1]
            self.sel = None
            self._blink = now
            return
        _, idx, col = hit
        text = self._wrapped()[idx][0]
        if count == 1:
            self.sel = ((idx, col), (idx, col))
            self.dragging = True
        elif count == 2:
            s, e = word_bounds(text, col)
            self.sel = ((idx, s), (idx, e)) if e > s else None
        else:
            self.sel = ((idx, 0), (idx, len(text)))

    def _on_key(self, event):
        k, mod, ed = event.key, event.mod, self.editor
        ctrl = bool(mod & (pygame.KMOD_CTRL | pygame.KMOD_META))
        if k in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._edit()
            line = ed.submit()
            self._append(self.prompt + line, ("echo", len(self.prompt)))
            return line
        if k == pygame.K_PAGEUP:
            self.scroll += max(1, self.rows - 2)
        elif k == pygame.K_PAGEDOWN:
            self.scroll = max(0, self.scroll - max(1, self.rows - 2))
        elif ctrl and k == pygame.K_c:
            self.copy()
        elif ctrl and k == pygame.K_v:
            self.paste()
        elif ctrl and k == pygame.K_l:
            self.clear()
        elif ctrl and k == pygame.K_a:
            self._edit(); ed.home()
        elif ctrl and k == pygame.K_e:
            self._edit(); ed.end()
        elif ctrl and k == pygame.K_k:
            self._edit(); ed.kill_to_end()
        elif ctrl and k == pygame.K_u:
            self._edit(); ed.kill_to_start()
        elif ctrl and k == pygame.K_w:
            self._edit(); ed.delete_word_back()
        elif k == pygame.K_BACKSPACE:
            self._edit()
            ed.delete_word_back() if ctrl else ed.backspace()
        elif k == pygame.K_DELETE:
            self._edit(); ed.delete()
        elif k == pygame.K_LEFT:
            self._edit()
            ed.word_left() if ctrl else ed.left()
        elif k == pygame.K_RIGHT:
            self._edit()
            ed.word_right() if ctrl else ed.right()
        elif k == pygame.K_HOME:
            self._edit(); ed.home()
        elif k == pygame.K_END:
            self._edit(); ed.end()
        elif k == pygame.K_UP:
            self._edit(); ed.history_prev()
        elif k == pygame.K_DOWN:
            self._edit(); ed.history_next()
        elif k == pygame.K_TAB:
            self._complete()
        return None

    # ------------------------------------------------------------ drawing
    def _blit_line(self, surface, text, style, x, y):
        if not text:
            return
        if isinstance(style, tuple):
            pre, post = text[:style[1]], text[style[1]:]
            surface.blit(self.font.render(pre, True, COLORS["prompt"]), (x, y))
            if post:
                surface.blit(self.font.render(post, True, COLORS["cmd"]),
                             (x + self.font.size(pre)[0], y))
        else:
            surface.blit(self.font.render(text, True, COLORS[style]), (x, y))

    def _draw_input(self, surface, x, y):
        ed, font = self.editor, self.font
        prompt_w = font.size(self.prompt)[0]
        avail = self.text_width - prompt_w - self.char_w
        if ed.pos < self.hscroll:
            self.hscroll = ed.pos
        while self.hscroll < ed.pos and font.size(ed.text[self.hscroll:ed.pos])[0] > avail:
            self.hscroll += 1
        shown = ed.text[self.hscroll:]
        shown = shown[:fit(font, shown, avail + self.char_w)]
        surface.blit(font.render(self.prompt, True, COLORS["prompt"]), (x, y))
        if shown:
            surface.blit(font.render(shown, True, COLORS["cmd"]), (x + prompt_w, y))
        cx = x + prompt_w + font.size(shown[:ed.pos - self.hscroll])[0]
        if (pygame.time.get_ticks() - self._blink) % 1000 < 600:
            pygame.draw.rect(surface, COLORS["cursor"], (cx, y, self.char_w, self.line_h))
            under = ed.text[ed.pos:ed.pos + 1]
            if under and under.strip():
                surface.blit(font.render(under, True, COLORS["term_bg"]), (cx, y))

    def draw(self, surface):
        pygame.draw.rect(surface, COLORS["term_bg"], self.rect)
        pygame.draw.rect(surface, (40, 120, 70), self.rect, 1)
        surface.set_clip(self.rect)
        w = self._wrapped()
        start, end = self._view()
        a, b = self._sel_range()
        x0, y = self.rect.x + PAD, self.rect.y + PAD
        for i in range(start, end):
            text, style, _ = w[i]
            if a is not None and a[0] <= i <= b[0]:
                s = a[1] if i == a[0] else 0
                e = b[1] if i == b[0] else len(text)
                x1, x2 = self.font.size(text[:s])[0], self.font.size(text[:e])[0]
                if i < b[0]:
                    x2 += self.char_w // 2
                if x2 > x1:
                    pygame.draw.rect(surface, COLORS["select"], (x0 + x1, y, x2 - x1, self.line_h))
            self._blit_line(surface, text, style, x0, y)
            y += self.line_h
        self._draw_input(surface, x0, y)
        small = self.font
        if self.scroll > 0:
            tag = small.render(" scrolled up - PageDown to return ", True, COLORS["term_bg"])
            pygame.draw.rect(surface, COLORS["info"], (self.rect.right - tag.get_width() - 8,
                                                      self.rect.y + 6, tag.get_width(), tag.get_height()))
            surface.blit(tag, (self.rect.right - tag.get_width() - 8, self.rect.y + 6))
        text, until = self._toast
        if text and pygame.time.get_ticks() < until:
            t = small.render(" " + text + " ", True, COLORS["term_bg"])
            tx = self.rect.right - t.get_width() - 10
            ty = self.rect.bottom - t.get_height() - 8
            pygame.draw.rect(surface, COLORS["good"], (tx, ty, t.get_width(), t.get_height()))
            surface.blit(t, (tx, ty))
        surface.set_clip(None)