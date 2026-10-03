"""
    ROOT ACCESS - a terminal hacking puzzle game built with Pygame.
"""
import glob
import json
import os
import sys

import pygame

import save
from commands import CLEAR, Shell
from terminal import Terminal
from ui import BG, BORDER, COLORS, PANEL, Menu, make_font, wrap_text

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_SIZES = [14, 16, 18, 20, 22, 24, 28, 32]

HOWTO = [
    ("good", "THE GOAL"),
    ("out", "Every level is a computer you have broken into. Explore it by typing commands, "
            "find the hidden flag (it looks like FLAG{...}) and hand it in with:  submit FLAG{...}"),
    ("", ""),
    ("good", "YOUR FIRST MOVES"),
    ("cmd", "ls            see the files here   (ls -a also shows hidden ones)"),
    ("cmd", "cd folder     go into a folder     (cd .. goes back up)"),
    ("cmd", "cat file      read a file"),
    ("cmd", "hint          stuck? get a hint (using hints lowers your star rating)"),
    ("cmd", "objective     remind yourself what to do"),
    ("info", "New commands unlock as you progress. Type 'help' any time to see what you have."),
    ("", ""),
    ("good", "TYPING"),
    ("out", "Tab                  auto-complete a command or file name (press twice to list options)"),
    ("out", "Up / Down            bring back earlier commands"),
    ("out", "Left / Right         move the cursor      Home / End: jump to start / end"),
    ("out", "Ctrl+Left / Right    jump by word         Ctrl+Backspace: delete a word"),
    ("out", "Ctrl+U               clear the line       (hold Backspace to delete fast)"),
    ("", ""),
    ("good", "COPY AND PASTE"),
    ("out", "Drag with the mouse to select text, or double-click a word. Ctrl+C copies it. "
            "Ctrl+V or right-click pastes into your command line."),
    ("", ""),
    ("good", "OTHER KEYS"),
    ("out", "Esc: menu     F1: this page     F2: show/hide the mission panel"),
    ("out", "Mouse wheel / PageUp / PageDown: scroll     Ctrl + and Ctrl -: text size"),
    ("", ""),
    ("good", "COLOURS"),
    ("out", "Green   normal output"),
    ("cmd", "White   what you typed"),
    ("error", "Red     errors"),
    ("hint", "Amber   hints and tips"),
    ("good", "Yellow  success and headings"),
    ("info", "Gray    notes from the system"),
    ("", ""),
    ("good", "STARS"),
    ("out", "3 stars: no hints.   2 stars: one or two hints.   1 star: three or more hints."),
]


def load_levels():
    levels = []
    for path in sorted(glob.glob(os.path.join(HERE, "levels", "*.json"))):
        with open(path, encoding="utf-8") as f:
            level = json.load(f)
        level["id"] = os.path.splitext(os.path.basename(path))[0]
        level.setdefault("objective", "Find the flag and submit it.")
        level.setdefault("hints", [])
        level.setdefault("intro", [])
        level.setdefault("start", [])
        levels.append(level)
    return levels


def star_text(n):
    return "[" + "*" * n + " " * (3 - n) + "]"


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("ROOT ACCESS")
        self.screen = pygame.display.set_mode((1100, 680), pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        pygame.key.start_text_input()

        self.levels = load_levels()
        if not self.levels:
            sys.exit("No levels found in %s" % os.path.join(HERE, "levels"))
        self.data = save.load()
        self.font_size = self.data["settings"].get("font_size", 20)
        if self.font_size not in FONT_SIZES:
            self.font_size = 20
        self.panel = bool(self.data["settings"].get("panel", True))

        self.fonts = {"ui": make_font(22), "small": make_font(16),
                      "mid": make_font(34, bold=True), "big": make_font(62, bold=True)}
        self.term = Terminal((0, 0, 400, 300), make_font(self.font_size))
        self.panel_rect = None
        self._size = (0, 0)
        self.relayout()

        self.shell = None
        self.level_index = 0
        self.prev_state = "menu"
        self.reset_armed = False
        self.howto_scroll = 0
        self.howto_max = 0
        self._howto_back = pygame.Rect(0, 0, 0, 0)
        self.state = "menu"
        self.menu = self.build_main()
        self.set_state("menu")

    # ------------------------------------------------------------------ state
    def set_state(self, state):
        self.state = state
        if state in ("playing", "howto"):
            pygame.key.set_repeat(400, 35)     # holding Backspace/arrows repeats
        else:
            pygame.key.set_repeat()            # no accidental repeated menu clicks

    def persist(self):
        self.data["settings"] = {"font_size": self.font_size, "panel": self.panel}
        save.save(self.data)

    def relayout(self):
        self.screen = pygame.display.get_surface()
        w, h = self.screen.get_size()
        self._size = (w, h)
        gap = 14
        panel_w = 330 if (self.panel and w >= 900) else 0
        term_w = w - 2 * gap - (panel_w + gap if panel_w else 0)
        body_h = h - 2 * gap - 26
        self.term.set_rect((gap, gap, term_w, body_h))
        self.panel_rect = pygame.Rect(w - gap - panel_w, gap, panel_w, body_h) if panel_w else None

    # ------------------------------------------------------------------ progress
    def completed(self, i):
        return self.levels[i]["id"] in self.data["stars"]

    def unlocked(self, i):
        return i == 0 or self.completed(i - 1)

    def next_level_index(self):
        for i in range(len(self.levels)):
            if not self.completed(i):
                return i
        return 0

    # ------------------------------------------------------------------ menus
    def build_main(self):
        done = sum(1 for i in range(len(self.levels)) if self.completed(i))
        if done == 0:
            first = "Start Game"
        elif done == len(self.levels):
            first = "Play Again"
        else:
            first = "Continue - Level %d" % (self.next_level_index() + 1)
        return Menu("ROOT ACCESS", [
            {"label": first, "action": "continue"},
            {"label": "Level Select", "action": "levels"},
            {"label": "How to Play", "action": "howto"},
            {"label": "Settings", "action": "settings"},
            {"label": "Quit", "action": "quit"},
        ], subtitle="a terminal hacking puzzle game   -   %d of %d levels cleared" % (done, len(self.levels)),
            footer="Up/Down + Enter, or use the mouse")

    def build_levels(self):
        items = []
        for i, lvl in enumerate(self.levels):
            if self.unlocked(i):
                stars = self.data["stars"].get(lvl["id"], 0)
                tail = star_text(stars) if self.completed(i) else "new"
                items.append({"label": "%d. %s   %s" % (i + 1, lvl["name"], tail),
                              "action": "pick:%d" % i})
            else:
                items.append({"label": "%d. %s   LOCKED" % (i + 1, lvl["name"]),
                              "action": "pick:%d" % i, "enabled": False})
        items.append({"label": "Back", "action": "back"})
        m = Menu("LEVEL SELECT", items, title_font="mid",
                 subtitle="Finish a level to unlock the next one.")
        m.sel = self.next_level_index()
        return m

    def build_settings(self, sel=0):
        items = [
            {"label": "Text size", "value": "< %d >" % self.font_size, "action": "font"},
            {"label": "Mission panel", "value": "ON" if self.panel else "OFF", "action": "panel"},
            {"label": "Reset progress",
             "value": "press again to confirm" if self.reset_armed else "erase all stars",
             "action": "reset"},
            {"label": "Back", "action": "back"},
        ]
        m = Menu("SETTINGS", items, title_font="mid",
                 footer="Up/Down: choose    Left/Right or Enter: change    Esc: back")
        m.sel = sel
        return m

    def build_pause(self):
        return Menu("PAUSED", [
            {"label": "Resume", "action": "resume"},
            {"label": "Restart Level", "action": "restart"},
            {"label": "How to Play", "action": "howto"},
            {"label": "Settings", "action": "settings"},
            {"label": "Main Menu", "action": "mainmenu"},
            {"label": "Quit", "action": "quit"},
        ], title_font="mid", footer="Esc: resume")

    def build_end(self):
        return Menu("ALL SYSTEMS COMPROMISED", [
            {"label": "Main Menu", "action": "mainmenu"},
            {"label": "Level Select", "action": "levels"},
            {"label": "Quit", "action": "quit"},
        ], title_font="mid", title_color="good",
            subtitle="You cleared all %d levels. Add more by dropping new JSON files into the levels folder."
                     % len(self.levels))

    # ------------------------------------------------------------------ level flow
    def start_level(self, index):
        self.level_index = index
        lvl = self.levels[index]
        self.shell = Shell(lvl)
        t = self.term
        t.clear()
        t.editor.set("")
        t.completer = self.shell.complete
        t.prompt = self.shell.prompt()
        t.print("=== LEVEL %d of %d: %s ===" % (index + 1, len(self.levels), lvl["name"]), "good")
        for line in lvl["intro"]:
            t.print(line, "out")
        t.print("", "out")
        t.print("Goal: " + lvl["objective"], "good")
        for line in lvl.get("tutorial", []):
            t.print(line, "hint")
        t.print("", "out")
        t.print("Type 'help' for commands - or 'hint' if you get stuck.", "info")
        t.print("", "out")
        self.set_state("playing")

    def finish_level(self):
        sh, lvl = self.shell, self.levels[self.level_index]
        stars = 3 if sh.hints_used == 0 else (2 if sh.hints_used <= 2 else 1)
        self.data["stars"][lvl["id"]] = max(self.data["stars"].get(lvl["id"], 0), stars)
        save.save(self.data)
        last = self.level_index + 1 >= len(self.levels)
        self.menu = Menu("ACCESS GRANTED", [
            {"label": "Finish" if last else "Next Level", "action": "next"},
            {"label": "Replay Level", "action": "replay"},
            {"label": "Main Menu", "action": "mainmenu"},
        ], subtitle="%s cleared   %s   hints used: %d   commands: %d"
                    % (lvl["name"], star_text(stars), sh.hints_used, sh.commands_run),
            title_font="mid", title_color="good", footer="Up/Down: choose    Enter: select")
        self.set_state("complete")

    def open_howto(self):
        self.prev_state = {"menu": "menu", "pause": "pause", "playing": "playing"}.get(self.state, "menu")
        self.howto_scroll = 0
        self.set_state("howto")

    def go_back(self):
        prev = self.prev_state
        if prev == "pause":
            self.menu = self.build_pause()
            self.set_state("pause")
        elif prev == "playing":
            self.set_state("playing")
        else:
            self.menu = self.build_main()
            self.set_state("menu")

    def change_font(self, step=None, reset=False):
        i = FONT_SIZES.index(self.font_size)
        if reset:
            i = FONT_SIZES.index(20)
        elif step is not None:
            i = max(0, min(len(FONT_SIZES) - 1, i + step))
        self.font_size = FONT_SIZES[i]
        self.term.set_font(make_font(self.font_size))
        self.persist()

    def do_action(self, action, delta=0):
        if action.startswith("pick:"):
            self.start_level(int(action.split(":")[1]))
        elif action == "continue":
            self.start_level(self.next_level_index())
        elif action == "levels":
            self.prev_state = "menu"
            self.menu = self.build_levels()
            self.set_state("levels")
        elif action == "howto":
            self.open_howto()
        elif action == "settings":
            self.prev_state = "pause" if self.state == "pause" else "menu"
            self.reset_armed = False
            self.menu = self.build_settings()
            self.set_state("settings")
        elif action == "back":
            self.go_back()
        elif action == "quit":
            self.quit()
        elif action == "resume":
            self.set_state("playing")
        elif action in ("restart", "replay"):
            self.start_level(self.level_index)
        elif action == "mainmenu":
            self.menu = self.build_main()
            self.set_state("menu")
        elif action == "next":
            if self.level_index + 1 < len(self.levels):
                self.start_level(self.level_index + 1)
            else:
                self.menu = self.build_end()
                self.set_state("end")
        elif action in ("font", "panel", "reset"):
            self.settings_action(action, delta)

    def settings_action(self, action, delta):
        sel = self.menu.sel
        if action == "font":
            if delta == 0:
                self.change_font(step=1 if self.font_size != FONT_SIZES[-1] else -(len(FONT_SIZES) - 1))
            else:
                self.change_font(step=delta)
        elif action == "panel":
            self.panel = not self.panel
            self.persist()
            self.relayout()
        elif action == "reset":
            if self.reset_armed:
                self.data["stars"] = {}
                save.save(self.data)
                self.reset_armed = False
            else:
                self.reset_armed = True
        self.menu = self.build_settings(sel)

    def quit(self):
        self.persist()
        pygame.quit()
        sys.exit()

    # ------------------------------------------------------------------ events
    def handle(self, event):
        if event.type == pygame.QUIT:
            self.quit()
        if self.state == "playing":
            self.on_playing(event)
        elif self.state == "howto":
            self.on_howto(event)
        else:
            self.on_menu(event)

    def on_menu(self, event):
        result = self.menu.handle_event(event)
        if not result:
            return
        action, delta = result
        if action == "__back__":
            if self.state == "pause":
                self.set_state("playing")
            elif self.state in ("levels", "settings"):
                self.go_back()
            elif self.state == "end":
                self.do_action("mainmenu")
            return
        self.do_action(action, delta)

    def on_howto(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_F1):
                self.go_back()
            elif event.key == pygame.K_UP:
                self.howto_scroll -= 40
            elif event.key == pygame.K_DOWN:
                self.howto_scroll += 40
            elif event.key == pygame.K_PAGEUP:
                self.howto_scroll -= 300
            elif event.key == pygame.K_PAGEDOWN:
                self.howto_scroll += 300
        elif event.type == pygame.MOUSEWHEEL:
            self.howto_scroll -= event.y * 40
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._howto_back.collidepoint(event.pos):
                self.go_back()
        self.howto_scroll = max(0, min(self.howto_max, self.howto_scroll))

    def on_playing(self, event):
        if event.type == pygame.KEYDOWN:
            ctrl = bool(event.mod & (pygame.KMOD_CTRL | pygame.KMOD_META))
            if event.key == pygame.K_ESCAPE:
                self.menu = self.build_pause()
                self.set_state("pause")
                return
            if event.key == pygame.K_F1:
                self.open_howto()
                return
            if event.key == pygame.K_F2:
                self.panel = not self.panel
                self.persist()
                self.relayout()
                return
            if ctrl and event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                self.change_font(step=1)
                return
            if ctrl and event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                self.change_font(step=-1)
                return
            if ctrl and event.key == pygame.K_0:
                self.change_font(reset=True)
                return
        line = self.term.handle_event(event)
        if line is None:
            return
        for text, style in self.shell.run(line):
            if text == CLEAR:
                self.term.clear()
            else:
                self.term.print(text, style)
        self.term.prompt = self.shell.prompt()
        if self.shell.solved:
            self.finish_level()

    # ------------------------------------------------------------------ drawing
    def draw_panel(self, rect):
        s, sm, ui = self.screen, self.fonts["small"], self.fonts["ui"]
        pygame.draw.rect(s, PANEL, rect)
        pygame.draw.rect(s, BORDER, rect, 1)
        s.set_clip(rect)
        x, width = rect.x + 14, rect.width - 28
        y = rect.y + 12

        def block(text, color, font=sm, gap=6):
            nonlocal y
            for ln in wrap_text(text, font, width):
                s.blit(font.render(ln, True, COLORS[color]), (x, y))
                y += font.get_linesize()
            y += gap

        lvl = self.levels[self.level_index]
        block("MISSION", "good", ui, 4)
        block("Level %d of %d: %s" % (self.level_index + 1, len(self.levels), lvl["name"]), "info")
        block(lvl["objective"], "out", sm, 14)
        block("HINTS", "good", ui, 4)
        block("Used %d of %d.  Type  hint" % (self.shell.hints_used, len(lvl["hints"])), "hint", sm, 14)
        block("COMMANDS", "good", ui, 4)
        for usage, _ in self.shell.help_entries():
            block(usage, "cmd", sm, 2)
        y += 12
        block("KEYS", "good", ui, 4)
        for tip in ("Tab  auto-complete", "Up/Down  old commands", "Drag / double-click  select",
                    "Ctrl+C / Ctrl+V  copy / paste", "Esc  menu     F1  how to play",
                    "F2  hide this panel"):
            block(tip, "info", sm, 2)
        s.set_clip(None)

    def draw_game(self):
        self.term.draw(self.screen)
        if self.panel_rect:
            self.draw_panel(self.panel_rect)
        w, h = self.screen.get_size()
        tip = "Tab: complete  |  Up/Down: history  |  Ctrl+C / Ctrl+V: copy / paste  |  Esc: menu  |  F1: help"
        self.screen.blit(self.fonts["small"].render(tip, True, COLORS["info"]), (16, h - 28))

    def draw_howto(self):
        s, ui = self.screen, self.fonts["ui"]
        w, h = s.get_size()
        box = pygame.Rect((w - min(920, w - 60)) // 2, 30, min(920, w - 60), h - 110)
        pygame.draw.rect(s, PANEL, box)
        pygame.draw.rect(s, BORDER, box, 2)
        rows = []
        for color, text in HOWTO:
            if not text:
                rows.append((None, "", 12))
                continue
            for ln in wrap_text(text, ui, box.width - 40):
                rows.append((color, ln, ui.get_linesize()))
        total = sum(r[2] for r in rows)
        self.howto_max = max(0, total - (box.height - 30))
        self.howto_scroll = max(0, min(self.howto_max, self.howto_scroll))
        s.set_clip(box.inflate(-4, -4))
        y = box.y + 16 - self.howto_scroll
        for color, ln, step in rows:
            if color and box.y - step < y < box.bottom:
                s.blit(ui.render(ln, True, COLORS[color]), (box.x + 20, y))
            y += step
        s.set_clip(None)
        label = ui.render("[ Back ]", True, COLORS["cmd"])
        self._howto_back = pygame.Rect(w // 2 - 70, h - 62, 140, 40)
        pygame.draw.rect(s, COLORS["bar"], self._howto_back)
        pygame.draw.rect(s, COLORS["out"], self._howto_back, 1)
        s.blit(label, (self._howto_back.centerx - label.get_width() // 2,
                       self._howto_back.centery - label.get_height() // 2))
        foot = self.fonts["small"].render("Up/Down or mouse wheel: scroll     Esc / Enter: back",
                                          True, COLORS["info"])
        s.blit(foot, (w // 2 - foot.get_width() // 2, h - 18))

    def draw(self):
        s = self.screen
        s.fill(BG)
        w, h = s.get_size()
        area = pygame.Rect(0, 0, w, h)
        if self.state in ("playing", "pause", "complete"):
            self.draw_game()
        if self.state in ("pause", "complete"):
            veil = pygame.Surface((w, h), pygame.SRCALPHA)
            veil.fill((0, 0, 0, 175))
            s.blit(veil, (0, 0))
            self.menu.draw(s, self.fonts, area, boxed=True)
        elif self.state in ("menu", "levels", "settings", "end"):
            self.menu.draw(s, self.fonts, area)
        elif self.state == "howto":
            self.draw_howto()
        pygame.display.flip()

    def run(self):
        while True:
            for event in pygame.event.get():
                self.handle(event)
            surf = pygame.display.get_surface()
            if surf.get_size() != self._size:
                self.relayout()
            self.draw()
            self.clock.tick(60)


if __name__ == "__main__":
    Game().run()