"""Copy/paste helper. Tries pygame.scrap, then common Linux tools, and always
keeps an in-game copy so copy -> paste works even if the OS clipboard fails."""
import shutil
import subprocess

import pygame

_internal = ""


def _scrap_ready():
    try:
        if not pygame.scrap.get_init():
            pygame.scrap.init()
        return True
    except Exception:
        return False


def copy(text):
    """Returns True if the text reached the system clipboard."""
    global _internal
    _internal = text
    try:
        if _scrap_ready():
            pygame.scrap.put(pygame.SCRAP_TEXT, text.encode("utf-8"))
            return True
    except Exception:
        pass
    for cmd in (["wl-copy"], ["xclip", "-selection", "clipboard"],
                ["xsel", "--clipboard", "--input"]):
        if shutil.which(cmd[0]):
            try:
                subprocess.run(cmd, input=text.encode("utf-8"), timeout=2, check=True)
                return True
            except Exception:
                continue
    return False


def paste():
    """Returns clipboard text ('' if nothing available)."""
    text = ""
    try:
        if _scrap_ready():
            data = pygame.scrap.get(pygame.SCRAP_TEXT)
            if data:
                text = data.decode("utf-8", "ignore").replace("\x00", "")
    except Exception:
        text = ""
    if not text:
        for cmd in (["wl-paste", "-n"], ["xclip", "-selection", "clipboard", "-o"],
                    ["xsel", "--clipboard", "--output"]):
            if shutil.which(cmd[0]):
                try:
                    r = subprocess.run(cmd, capture_output=True, timeout=2)
                    if r.returncode == 0 and r.stdout:
                        text = r.stdout.decode("utf-8", "ignore")
                        break
                except Exception:
                    continue
    return text or _internal