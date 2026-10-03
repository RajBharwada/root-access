# ROOT ACCESS
#### Video Demo: https://youtu.be/s_NeoKQB-Bs
#### Description:

ROOT ACCESS is a hacking puzzle game that runs inside a fake terminal. You play someone who has broken into a series of computers. On each one you type commands like `ls`, `cd`, `cat` and `grep` to dig around until you find a hidden flag, then you hand it in with `submit FLAG{...}` to move on to the next machine. I built it with Python and Pygame for my CS50x final project.

I chose this idea for two reasons. First, I'm teaching myself cybersecurity, and I wanted a project that would actually help me learn instead of a game with a hacking theme stuck on top. Every level is built around one real idea: hidden files, encoded text, a simple cipher, and reading a log file to catch an attacker. Second, I really didn't want to spend my time drawing sprites. A terminal game only needs text and a font, so almost all of my effort went into the mechanics and into making the typing feel good.

## How to run it

You need Python 3.10 or newer and Pygame.

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

On Windows, activate the environment with `.venv\Scripts\activate` instead.

## How it plays

The main menu lets you start or continue the game, pick a level, read the How to Play page, or change settings. Inside a level, the big panel on the left is the terminal and the panel on the right is a mission panel. It shows your objective, the commands you currently have, and the most useful keys.

There are four levels:

1. **First Contact** teaches `ls`, `cd` and `cat`. The flag is in a hidden folder, so you have to learn that `ls -a` shows hidden files.
2. **Obfuscation** unlocks `decode`. The flag is stored as base64, which looks scrambled but isn't encryption.
3. **Caesar's Mailbox** adds the Caesar cipher to `decode`. You read a note, work out the shift, and undo it.
4. **Brute Force** unlocks `grep`. You search an SSH log for failed logins and find the one IP address that tried again and again, then got in.

If you get stuck, the `hint` command gives up to three hints per level, each a bit more revealing than the last. Each level is rated from one to three stars: three for no hints, two for one or two hints, one for more. Progress and settings are saved in a small JSON file in the home folder, so the game remembers where you left off.

## What each file does

- **main.py** is the heart of the game. It contains the `Game` class, which runs the main loop and switches between states (menu, level select, settings, playing, paused, level complete, end screen, How to Play). It also loads the levels, draws the mission panel, and handles keyboard shortcuts like Esc, F1, F2 and text zoom.
- **terminal.py** is the terminal widget. It keeps the scrollback, wraps long lines, draws the prompt and cursor, and handles mouse selection (drag, double-click a word, triple-click a line), copy and paste, and Tab completion.
- **lineedit.py** is the text editor for the command line: cursor movement, jumping by word, deleting, and command history. It deliberately doesn't import Pygame, which made it easy to test on its own.
- **clipboard.py** handles copy and paste.
- **commands.py** is the fake shell. It holds the commands (`ls`, `cd`, `cat`, `pwd`, `grep`, `decode`, `submit`, `hint`, `objective`, `clear`, `help`) and the Tab-completion logic.
- **ui.py** holds the color palette, font loading, text-wrapping helpers, and the reusable `Menu` class used by every menu in the game.
- **save.py** reads and writes the save file.
- **ciphers.py** contains the base64 and Caesar helpers behind `decode`.
- **levels/*.json** are the levels. Each one describes a fake filesystem, the intro text, the objective, the hints, the flag, and which commands are available.
- **requirements.txt** lists the one dependency, Pygame.

## Design choices, and what went wrong along the way

**The filesystem is fake.** The commands never touch the real computer. Each level has a small filesystem stored as nested dictionaries inside a JSON file, and `ls`, `cd` and `cat` just walk through it. That keeps the game safe, and it also means a new level is just a new JSON file with no code changes.

**Commands unlock gradually.** Each level lists which commands exist. If you try one that hasn't been unlocked, the game says it isn't installed on that machine yet. I did this so every level teaches exactly one new tool instead of dumping everything on the player at once.

**The typing was the hardest part.** My first version was embarrassingly bad: I couldn't copy or paste, I couldn't move the cursor with the arrow keys, and holding Backspace did nothing. I rewrote it properly. Typed characters now come from Pygame's `TEXTINPUT` events, and editing keys come from `KEYDOWN` with `pygame.key.set_repeat` turned on, so holding a key works. I also added history, word jumping, Tab completion and mouse selection. Tab completion deliberately skips hidden files unless you type the dot, because otherwise it would give away level 1.

**Copy and paste needed a fallback.** Pygame's clipboard support can fail depending on the desktop, so `clipboard.py` tries Pygame first, then tools like `wl-copy` and `xclip`, and finally keeps its own copy inside the game. Copying text from the terminal and pasting it into a command always works, which matters on level 2.

**One color for one meaning.** At first the output looked randomly bright or dark because I'd used a dim color for echoed commands. Now each color has one job: green is output, white is what you typed, red is errors, amber is hints, and yellow is success.

**Commands are parsed with `shlex`.** That lets players write quoted searches like `grep "Failed password" auth.log`, which feels more like a real shell.

**Hints cost stars.** I wanted hints to be available so nobody gets permanently stuck, but not free, so the star rating gives a reason to try first.

## What I'd add next

A trace timer that rises while you work, to add pressure. More levels, for example one that mixes several tools. A level where you have to find and read more than one log. Sound effects would also be nice.
