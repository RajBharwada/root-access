"""Pure-Python single-line text editor (no pygame): cursor, history, word moves."""

MAX_LEN = 300


def clean(text, paste=False):
    """Strip control characters. Pasted newlines/tabs become spaces."""
    if paste:
        for bad in ("\r\n", "\n", "\r", "\t"):
            text = text.replace(bad, " ")
    return "".join(ch for ch in text if ch.isprintable())


class LineEditor:
    def __init__(self):
        self.text = ""
        self.pos = 0                 # cursor position (0..len(text))
        self.history = []
        self._hist_i = 0
        self._draft = ""

    # ---- basic editing ----
    def set(self, text):
        self.text = text
        self.pos = len(text)

    def insert(self, s, paste=False):
        s = clean(s, paste)
        if not s:
            return
        s = s[:max(0, MAX_LEN - len(self.text))]
        self.text = self.text[:self.pos] + s + self.text[self.pos:]
        self.pos += len(s)

    def backspace(self):
        if self.pos > 0:
            self.text = self.text[:self.pos - 1] + self.text[self.pos:]
            self.pos -= 1

    def delete(self):
        if self.pos < len(self.text):
            self.text = self.text[:self.pos] + self.text[self.pos + 1:]

    # ---- cursor movement ----
    def left(self):
        self.pos = max(0, self.pos - 1)

    def right(self):
        self.pos = min(len(self.text), self.pos + 1)

    def home(self):
        self.pos = 0

    def end(self):
        self.pos = len(self.text)

    def _word_left_index(self):
        i = self.pos
        while i > 0 and self.text[i - 1].isspace():
            i -= 1
        while i > 0 and not self.text[i - 1].isspace():
            i -= 1
        return i

    def word_left(self):
        self.pos = self._word_left_index()

    def word_right(self):
        i, n = self.pos, len(self.text)
        while i < n and not self.text[i].isspace():
            i += 1
        while i < n and self.text[i].isspace():
            i += 1
        self.pos = i

    # ---- bulk deletes ----
    def delete_word_back(self):
        j = self._word_left_index()
        self.text = self.text[:j] + self.text[self.pos:]
        self.pos = j

    def kill_to_end(self):
        self.text = self.text[:self.pos]

    def kill_to_start(self):
        self.text = self.text[self.pos:]
        self.pos = 0

    # ---- history ----
    def submit(self):
        line = self.text
        if line.strip() and (not self.history or self.history[-1] != line):
            self.history.append(line)
        self.text, self.pos = "", 0
        self._hist_i = len(self.history)
        self._draft = ""
        return line

    def history_prev(self):
        if not self.history:
            return
        if self._hist_i == len(self.history):
            self._draft = self.text
        if self._hist_i > 0:
            self._hist_i -= 1
            self.set(self.history[self._hist_i])

    def history_next(self):
        if self._hist_i < len(self.history):
            self._hist_i += 1
            if self._hist_i == len(self.history):
                self.set(self._draft)
            else:
                self.set(self.history[self._hist_i])