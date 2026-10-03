"""The fake shell the player types into. Each cmd_<name> method is one command.
Levels choose which commands exist, so new tools are taught one at a time."""
import os
import shlex

import ciphers

CLEAR = "\x00clear"   # marker telling main.py to wipe the screen

# name -> (usage, one-line description). Display order = ORDER.
INFO = {
    "ls": ("ls [-a] [folder]", "list files (-a also shows hidden ones)"),
    "cd": ("cd <folder>", "enter a folder ('cd ..' goes back up)"),
    "cat": ("cat <file>", "show what is inside a file"),
    "pwd": ("pwd", "show which folder you are in"),
    "grep": ("grep [-i] [-c] <text> <file>",
             "show lines of a file containing <text> (-i ignore case, -c count)"),
    "decode": ("decode b64|caesar ...", "decode hidden text"),
    "submit": ("submit <flag>", "hand in the flag to finish the level"),
    "hint": ("hint", "get a hint (more hints = fewer stars)"),
    "objective": ("objective", "show what you must do on this level"),
    "clear": ("clear", "clear the screen"),
    "help": ("help", "show this list"),
}
ORDER = ["ls", "cd", "cat", "pwd", "grep", "decode", "submit",
         "hint", "objective", "clear", "help"]
ALWAYS = {"help", "hint", "objective", "clear"}


class Shell:
    def __init__(self, level):
        self.level = level
        self.root = level["fs"]
        self.start = list(level.get("start", []))
        self.cwd = list(self.start)
        self.solved = False
        self.hints_used = 0
        self.commands_run = 0
        wanted = level.get("commands")
        self.available = set(INFO) if wanted is None else (set(wanted) | ALWAYS)
        self.decode_modes = level.get("decode_modes", ["b64", "caesar"])

    # ---------------------------------------------------------- filesystem
    def _get(self, parts):
        node = self.root
        for p in parts:
            if not isinstance(node, dict) or p not in node:
                return None
            node = node[p]
        return node

    def _resolve(self, path):
        parts = [] if path.startswith("/") else list(self.cwd)
        for seg in path.split("/"):
            if seg in ("", "."):
                continue
            if seg == "..":
                if parts:
                    parts.pop()
            else:
                parts.append(seg)
        return parts

    def prompt(self):
        return "%s:/%s$ " % (self.level.get("host", "target"), "/".join(self.cwd))

    # ---------------------------------------------------------- help data
    def help_entries(self):
        rows = []
        for name in ORDER:
            if name not in self.available:
                continue
            if name == "decode":
                if "b64" in self.decode_modes:
                    rows.append(("decode b64 <text>", "decode base64 text"))
                if "caesar" in self.decode_modes:
                    rows.append(("decode caesar <n> <text>",
                                 "shift every letter by n (use a negative n to go back)"))
            else:
                rows.append(INFO[name])
        return rows

    # ---------------------------------------------------------- dispatcher
    def run(self, line):
        """Returns a list of (text, style) tuples to print."""
        line = line.strip()
        if not line:
            return []
        try:
            parts = shlex.split(line)
        except ValueError:
            return [("Unbalanced quote - close it with a matching \" or '.", "error")]
        cmd, args = parts[0], parts[1:]
        if cmd not in INFO:
            return [("%s: command not found. Type 'help' to see what you can use." % cmd, "error")]
        if cmd not in self.available:
            return [("%s: not installed on this machine yet." % cmd, "error")]
        self.commands_run += 1
        return getattr(self, "cmd_" + cmd)(args)

    # ---------------------------------------------------------- tab completion
    def _path_options(self, word):
        if "/" in word:
            dir_str, base = word.rsplit("/", 1)
            dir_str += "/"
            parts = self._resolve(dir_str)
        else:
            dir_str, base, parts = "", word, list(self.cwd)
        node = self._get(parts)
        if not isinstance(node, dict):
            return []
        out = []
        for name in sorted(node):
            if name.startswith(base) and (not name.startswith(".") or base.startswith(".")):
                suffix = "/" if isinstance(node[name], dict) else ""
                out.append((dir_str + name + suffix, name + suffix))
        return out

    def _arg_options(self, tokens, word):
        cmd, idx = tokens[0], len(tokens) - 1
        if cmd not in self.available or word.startswith("-"):
            return []
        if cmd in ("ls", "cd", "cat"):
            return self._path_options(word)
        if cmd == "grep" and idx >= 2:
            return self._path_options(word)
        if cmd == "decode" and idx == 1:
            return [(m, m) for m in self.decode_modes if m.startswith(word)]
        return []

    def complete(self, before):
        """Tab completion. Returns (new_text_before_cursor, list_of_options)."""
        tokens = before.split(" ")
        word = tokens[-1]
        head = " ".join(tokens[:-1]) + " " if len(tokens) > 1 else ""
        if len(tokens) == 1:
            opts = [(n, n) for n in sorted(self.available) if n.startswith(word)]
        else:
            opts = self._arg_options(tokens, word)
        if not opts:
            return before, []
        reps = [r for r, _ in opts]
        if len(opts) == 1:
            new = reps[0] if reps[0].endswith("/") else reps[0] + " "
        else:
            common = os.path.commonprefix(reps)
            new = common if len(common) > len(word) else word
        return head + new, [d for _, d in opts]

    # ---------------------------------------------------------- commands
    def cmd_help(self, args):
        out = [("Commands you can use here:", "good")]
        width = max(len(u) for u, _ in self.help_entries())
        for usage, desc in self.help_entries():
            out.append(("  %s  %s" % (usage.ljust(width), desc), "out"))
        out.append(("", "out"))
        out.append(("Tips: Tab completes names - Up/Down repeats commands - Esc opens the menu.", "hint"))
        return out

    def cmd_hint(self, args):
        hints = self.level.get("hints", [])
        if not hints:
            return [("No hints for this level - you've got this.", "hint")]
        if self.hints_used < len(hints):
            self.hints_used += 1
            return [("Hint %d/%d: %s" % (self.hints_used, len(hints), hints[self.hints_used - 1]), "hint")]
        return [("No more hints. Last one: %s" % hints[-1], "hint")]

    def cmd_objective(self, args):
        return [("Objective: " + self.level.get("objective", "Find the flag."), "good")]

    def cmd_clear(self, args):
        return [(CLEAR, "out")]

    def cmd_pwd(self, args):
        return [("/" + "/".join(self.cwd), "out")]

    def cmd_ls(self, args):
        show_all = "-a" in args
        paths = [a for a in args if a != "-a"]
        parts = self._resolve(paths[0]) if paths else self.cwd
        node = self._get(parts)
        if node is None:
            return [("ls: no such file or folder", "error")]
        if not isinstance(node, dict):
            return [(parts[-1], "out")]
        names = sorted(n for n in node if show_all or not n.startswith("."))
        lines = [(n + ("/" if isinstance(node[n], dict) else ""), "out") for n in names]
        return lines or [("(empty)", "info")]

    def cmd_cd(self, args):
        if not args:
            self.cwd = list(self.start)
            return []
        parts = self._resolve(args[0])
        if not isinstance(self._get(parts), dict):
            return [("cd: that's not a folder (use 'ls' to see what is here)", "error")]
        self.cwd = parts
        return []

    def cmd_cat(self, args):
        if not args:
            return [("usage: cat <file>", "error")]
        node = self._get(self._resolve(args[0]))
        if node is None:
            return [("cat: no such file", "error")]
        if isinstance(node, dict):
            return [("cat: that's a folder - use 'ls' or 'cd' instead", "error")]
        return [(t, "out") for t in node.split("\n")]

    def cmd_grep(self, args):
        flags = "".join(a[1:] for a in args if a.startswith("-") and len(a) > 1)
        rest = [a for a in args if not (a.startswith("-") and len(a) > 1)]
        if len(rest) < 2 or any(c not in "ic" for c in flags):
            return [("usage: grep [-i] [-c] <text> <file>", "error")]
        pattern, path = rest[0], rest[1]
        node = self._get(self._resolve(path))
        if not isinstance(node, str):
            return [("grep: %s: no such file" % path, "error")]
        needle = pattern.lower() if "i" in flags else pattern
        hits = [ln for ln in node.split("\n")
                if needle in (ln.lower() if "i" in flags else ln)]
        if "c" in flags:
            return [(str(len(hits)), "good")]
        return [(ln, "out") for ln in hits] or [("(no matching lines)", "info")]

    def cmd_decode(self, args):
        if len(args) >= 2 and args[0] == "b64" and "b64" in self.decode_modes:
            result = ciphers.b64_decode("".join(args[1:]))
            if result is None:
                return [("decode: that isn't valid base64 - did you copy all of it?", "error")]
            return [(result, "good")]
        if (len(args) >= 3 and args[0] == "caesar" and "caesar" in self.decode_modes
                and args[1].lstrip("-").isdigit()):
            return [(ciphers.caesar(" ".join(args[2:]), int(args[1])), "good")]
        usage = []
        if "b64" in self.decode_modes:
            usage.append("decode b64 <text>")
        if "caesar" in self.decode_modes:
            usage.append("decode caesar <n> <text>")
        return [("usage: " + "   or   ".join(usage), "error")]

    def cmd_submit(self, args):
        if not args:
            return [("usage: submit <flag>   (example: submit FLAG{...})", "error")]
        guess = " ".join(args).strip()
        if guess == self.level["flag"]:
            self.solved = True
            return [("ACCESS GRANTED.", "good")]
        if not guess.startswith("FLAG{"):
            return [("That doesn't look like a flag. Flags look like FLAG{...} - copy the whole thing.", "error")]
        return [("Wrong flag. Keep digging - or type 'hint'.", "error")]