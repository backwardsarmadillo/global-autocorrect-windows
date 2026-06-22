import ctypes
import importlib.resources
import json
import logging
import math
import re
import sys
import threading
import time
import winsound
from pathlib import Path

import keyboard
import mouse
import psutil
from symspellpy import SymSpell, Verbosity

import winspell


if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "global_autocorrect_config.json"
LOG_PATH = APP_DIR / "global_autocorrect.log"

DEFAULT_CONFIG = {
    "enabled": True,
    "log_corrections": False,
    "engine": "windows",
    "max_edit_distance": 3,
    "min_word_length": 2,
    "correct_capitalized": True,
    "correct_real_words": False,
    "idle_reset_seconds": 3,
    "toggle_beep": True,
    "auto_undo": True,
    "hotkeys": {
        "toggle": "ctrl+alt+a",
        "exit": "ctrl+alt+esc",
    },
    "blocked_processes": [
        "WindowsTerminal.exe",
        "wt.exe",
        "cmd.exe",
        "powershell.exe",
        "pwsh.exe",
        "Code.exe",
        "Cursor.exe",
        "devenv.exe",
        "notepad++.exe",
        "AutoHotkey.exe",
        "AutoHotkey64.exe",
        "python.exe",
        "pythonw.exe",
        "KeePass.exe",
        "KeePassXC.exe",
        "Bitwarden.exe",
        "1Password.exe",
        "steam.exe",
        "RiotClientServices.exe",
    ],
    "never_correct": [
        "ai",
        "api",
        "autocorrect",
        "chatgpt",
        "claude",
        "codex",
        "github",
        "gmail",
        "iphone",
        "microsoft",
        "openai",
        "teams",
        "ty",
        "ui",
        "ux",
        "windows",
    ],
    "manual_replacements": {
        "adn": "and",
        "agian": "again",
        "ahve": "have",
        "alot": "a lot",
        "anythign": "anything",
        "anytjing": "anything",
        "antyhgkn": "anything",
        "becuase": "because",
        "beleive": "believe",
        "brocolli": "broccoli",
        "cant": "can't",
        "couldnt": "couldn't",
        "definately": "definitely",
        "didnt": "didn't",
        "doesnt": "doesn't",
        "dont": "don't",
        "everythign": "everything",
        "fukcing": "fucking",
        "goig": "going",
        "goign": "going",
        "gonna": "gonna",
        "havent": "haven't",
        "helllo": "hello",
        "hyou": "you",
        "hte": "the",
        "im": "I'm",
        "ill": "I'll",
        "isnt": "isn't",
        "itll": "it'll",
        "its": "it's",
        "ive": "I've",
        "jsut": "just",
        "knwo": "know",
        "liek": "like",
        "necesary": "necessary",
        "neccessary": "necessary",
        "occured": "occurred",
        "peice": "piece",
        "probelm": "problem",
        "probly": "probably",
        "recieve": "receive",
        "seperate": "separate",
        "shoud": "should",
        "shhould": "should",
        "shoudl": "should",
        "shuld": "should",
        "somethign": "something",
        "shouldnt": "shouldn't",
        "taht": "that",
        "teh": "the",
        "theres": "there's",
        "thier": "their",
        "thoghts": "thoughts",
        "tht": "that",
        "thsi": "this",
        "tihs": "this",
        "tommorow": "tomorrow",
        "wanna": "wanna",
        "wasnt": "wasn't",
        "werent": "weren't",
        "whats": "what's",
        "wont": "won't",
        "wrok": "work",
        "wouldnt": "wouldn't",
        "youre": "you're",
        "yuo": "you",
    },
}

SEPARATORS = {
    "space": " ",
    ".": ".",
    ",": ",",
    ";": ";",
    ":": ":",
    "?": "?",
    "!": "!",
    ")": ")",
    "]": "]",
    "}": "}",
}

WORD_RE = re.compile(r"^[A-Za-z']+$")

logging.basicConfig(
    filename=str(LOG_PATH),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


def load_config():
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
        return DEFAULT_CONFIG
    config = DEFAULT_CONFIG | json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    config["hotkeys"] = DEFAULT_CONFIG["hotkeys"] | config.get("hotkeys", {})
    config["manual_replacements"] = (
        DEFAULT_CONFIG["manual_replacements"] | config.get("manual_replacements", {})
    )
    return config


config = load_config()
enabled = bool(config["enabled"])
buffer = []
last_keypress = 0.0
replacing = False
# Details of the most recent autocorrect (original, corrected, separator) while
# it is still "fresh" enough to revert with an immediate Backspace. Cleared as
# soon as the user does anything else, so a later Backspace deletes normally.
last_correction = None
# The previous committed word (lowercased), used as left-hand context for the
# next correction. Reset at sentence boundaries and whenever the buffer drops.
prev_word = ""
should_exit = threading.Event()
# Handle to the named mutex that enforces single-instance. Kept alive for the
# whole process; if it is garbage collected the lock is released.
_single_instance_handle = None


def reset_buffer(*_args):
    # Any caret-moving event (mouse click, idle gap) invalidates the pending
    # word, because our character-count-based backspacing assumes the caret is
    # still at the end of what we have buffered. This mirrors AutoHotkey's
    # default of clearing the hotstring recognizer on every mouse click.
    global buffer, last_correction, prev_word
    buffer = []
    # A click moves the caret, so the just-corrected word is no longer directly
    # behind it; reverting now would chew through unrelated text, and the
    # left-context word can no longer be trusted either.
    last_correction = None
    prev_word = ""


def foreground_process_name():
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    pid = ctypes.c_ulong()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""
    try:
        return psutil.Process(pid.value).name()
    except psutil.Error:
        return ""


def is_blocked_context():
    return foreground_process_name() in set(config["blocked_processes"])


def build_spellchecker():
    sym_spell = SymSpell(
        max_dictionary_edit_distance=int(config["max_edit_distance"]),
        prefix_length=7,
    )
    bundled_dictionary_path = APP_DIR / "frequency_dictionary_en_82_765.txt"
    if bundled_dictionary_path.exists():
        dictionary_path = bundled_dictionary_path
    else:
        dictionary_path = (
            importlib.resources.files("symspellpy") / "frequency_dictionary_en_82_765.txt"
        )
    sym_spell.load_dictionary(str(dictionary_path), term_index=0, count_index=1)

    # Word-pair frequencies give us context: how likely is this word right after
    # the previous one. Ships with symspellpy, so no extra download.
    bundled_bigrams = APP_DIR / "frequency_bigramdictionary_en_243_342.txt"
    if bundled_bigrams.exists():
        bigram_path = bundled_bigrams
    else:
        bigram_path = (
            importlib.resources.files("symspellpy")
            / "frequency_bigramdictionary_en_243_342.txt"
        )
    sym_spell.load_bigram_dictionary(str(bigram_path), term_index=0, count_index=2)

    for word in config["never_correct"]:
        sym_spell.create_dictionary_entry(word.lower(), 10_000_000_000)
    return sym_spell


spellchecker = build_spellchecker()


def apply_case(original, correction):
    if original.isupper():
        return correction.upper()
    if original[:1].isupper():
        return correction[:1].upper() + correction[1:]
    return correction


# --- Keyboard-geometry model -------------------------------------------------
# Staggered QWERTY coordinates so a substitution between physically close keys
# ('r'->'t') is treated as far more likely than between distant ones ('r'->'p').
# Plain edit distance cannot make that distinction; most real typos are slips
# onto a neighbouring key.
_QWERTY_ROWS = ("qwertyuiop", "asdfghjkl", "zxcvbnm")
_KEY_POS = {}
for _r, _row in enumerate(_QWERTY_ROWS):
    for _c, _ch in enumerate(_row):
        _KEY_POS[_ch] = (_r, _c + _r * 0.5)


def _sub_cost(a, b):
    if a == b:
        return 0.0
    pa, pb = _KEY_POS.get(a), _KEY_POS.get(b)
    if pa is None or pb is None:
        return 1.0
    dist = ((pa[0] - pb[0]) ** 2 + (pa[1] - pb[1]) ** 2) ** 0.5
    return 0.35 if dist <= 1.15 else 1.0


def keyboard_distance(a, b):
    # Damerau-Levenshtein where substitutions between neighbouring keys are
    # cheap and an adjacent transposition ("teh"->"the") is nearly free.
    la, lb = len(a), len(b)
    dp = [[0.0] * (lb + 1) for _ in range(la + 1)]
    for i in range(la + 1):
        dp[i][0] = i
    for j in range(lb + 1):
        dp[0][j] = j
    for i in range(1, la + 1):
        for j in range(1, lb + 1):
            cost = _sub_cost(a[i - 1], b[j - 1])
            dp[i][j] = min(
                dp[i - 1][j] + 1.0, dp[i][j - 1] + 1.0, dp[i - 1][j - 1] + cost
            )
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                dp[i][j] = min(dp[i][j], dp[i - 2][j - 2] + 0.7)
    return dp[la][lb]


# Blend weights for ranking candidates. Spelling proximity dominates; context
# and raw frequency break ties; rank nudges us toward the engine's own ordering.
_W_KB = 4.0
_W_CTX = 1.3
_W_FREQ = 1.0
_W_RANK = 0.5


def correction_for(word):
    if not WORD_RE.match(word):
        return word

    lower = word.lower()
    if lower in set(config["never_correct"]):
        return word

    manual = config["manual_replacements"].get(lower)
    if manual:
        return apply_case(word, manual)

    if len(word) < int(config["min_word_length"]):
        return "I" if word == "i" else word

    # By default (mega-aggressive) we also correct Capitalized words, so
    # sentence-start and capitalized typos get fixed; apply_case puts the
    # original capitalization back on the replacement. Set correct_capitalized
    # to false to leave Title-case words (usually proper nouns) untouched.
    if (
        not config.get("correct_capitalized", True)
        and word[:1].isupper()
        and not word.isupper()
    ):
        return word

    # Gather candidates. Preferred engine is the Windows spell checker
    # (Microsoft's dictionary, the same one behind the red squiggles), which
    # also simply declines to flag correctly spelled words. SymSpell is the
    # fallback when the API is unavailable.
    win = winspell.suggest(lower) if config.get("engine", "windows") == "windows" else None

    if win is not None:
        if not win:
            return word  # Windows considers it correctly spelled
        candidates = win
        counts = {c: spellchecker.words.get(c.lower(), 1) for c in candidates}
        ranks = {c: i for i, c in enumerate(candidates)}
    else:
        found = spellchecker.lookup(
            lower,
            Verbosity.ALL,
            max_edit_distance=int(config["max_edit_distance"]),
            include_unknown=False,
        )
        if not found:
            return word
        found.sort(key=lambda s: (s.distance, -s.count))
        found = found[:30]
        candidates = [s.term for s in found]
        counts = {s.term: s.count for s in found}
        ranks = {s.term: i for i, s in enumerate(found)}
        # Without Windows to vouch for it, guard correctly spelled words.
        if lower in spellchecker.words and not config.get("correct_real_words", False):
            return word

    # Re-rank the engine's candidates by keyboard geometry + context + frequency,
    # nudged toward the engine's own ordering, and take the winner.
    best_term, best_score = None, float("inf")
    for c in candidates:
        cl = c.lower()
        context = spellchecker.bigrams.get(f"{prev_word} {cl}", 0) if prev_word else 0
        score = (
            _W_KB * keyboard_distance(lower, cl)
            - _W_CTX * math.log10(context + 1)
            - _W_FREQ * math.log10(counts[c] + 1)
            + _W_RANK * ranks[c]
        )
        if score < best_score:
            best_score, best_term = score, c

    if best_term is None or best_term.lower() == lower:
        return word

    return apply_case(word, best_term)


def replace_previous_word(word, separator):
    global replacing, last_correction
    corrected = correction_for(word)
    if corrected == word:
        return word
    replacing = True
    try:
        keyboard.send("backspace", do_press=True, do_release=True)
        for _ in word:
            keyboard.send("backspace", do_press=True, do_release=True)
        keyboard.write(corrected + separator, delay=0)
        if config.get("log_corrections", False):
            logging.info(
                "Corrected %r -> %r in %s",
                word,
                corrected,
                foreground_process_name(),
            )
    finally:
        time.sleep(0.03)
        replacing = False
    # Arm the one-shot undo: if the very next key is Backspace, we put the
    # user's original spelling back. Mirrors phone keyboards, where deleting
    # right after an autocorrect restores exactly what you typed.
    if config.get("auto_undo", True):
        last_correction = (word, corrected, separator)
    return corrected


def revert_correction(original, corrected, separator):
    # The user hit Backspace immediately after an autocorrect. Their physical
    # Backspace has already removed the trailing separator, leaving the
    # corrected word in front of the caret; delete that and retype what they
    # originally had, separator included, so the net effect is a clean undo.
    global replacing
    replacing = True
    try:
        for _ in corrected:
            keyboard.send("backspace", do_press=True, do_release=True)
        keyboard.write(original + separator, delay=0)
    finally:
        time.sleep(0.03)
        replacing = False


def on_press(event):
    global buffer, last_keypress, last_correction, prev_word
    if replacing:
        return

    name = event.name
    if name in ("shift", "ctrl", "alt", "alt gr", "windows", "menu"):
        return

    # The undo window lasts exactly one keystroke: consume the armed correction
    # now. If this key turns out to be Backspace we revert below; any other key
    # means the moment has passed and the correction stands.
    pending_undo = last_correction
    last_correction = None

    # Drop a stale pending word after an inactivity gap. A long pause usually
    # means the user looked away, clicked, or switched focus, so the buffer can
    # no longer be trusted to match the text in front of the caret.
    now = time.monotonic()
    idle_limit = float(config.get("idle_reset_seconds", 3) or 0)
    if idle_limit > 0 and (now - last_keypress) > idle_limit:
        if buffer:
            buffer = []
        # After a pause the caret may have moved, so a blind revert is unsafe
        # and the left-context word is stale.
        pending_undo = None
        prev_word = ""
    last_keypress = now

    if not enabled or is_blocked_context():
        buffer = []
        prev_word = ""
        return

    if name in SEPARATORS:
        word = "".join(buffer)
        buffer = []
        if word:
            committed = replace_previous_word(word, SEPARATORS[name])
            # End-of-sentence punctuation starts a fresh context; otherwise the
            # word we just committed becomes the left context for the next one.
            prev_word = "" if name in (".", "!", "?") else committed.lower()
        elif name in (".", "!", "?"):
            prev_word = ""
        return

    if name == "backspace":
        if pending_undo is not None and not buffer:
            revert_correction(*pending_undo)
            return
        if buffer:
            buffer.pop()
        return

    if name in ("enter", "tab", "esc", "delete", "up", "down", "left", "right"):
        buffer = []
        prev_word = ""
        return

    if len(name) == 1 and (name.isalpha() or name == "'"):
        buffer.append(name)
        if len(buffer) > 48:
            buffer = buffer[-48:]
        return

    buffer = []


def toggle():
    global enabled, buffer, last_correction, prev_word
    enabled = not enabled
    buffer = []
    last_correction = None
    prev_word = ""
    logging.info("Global autocorrect %s", "enabled" if enabled else "paused")
    print(f"Global autocorrect {'enabled' if enabled else 'paused'}")
    if config.get("toggle_beep", True):
        # Audible state cue: rising tone on enable, falling tone on pause. The
        # windowless exe has no other way to tell the user which state it is in.
        try:
            winsound.Beep(880 if enabled else 440, 120)
        except RuntimeError:
            pass


def acquire_single_instance_lock():
    # Refuse to launch a second copy. Two global keyboard hooks both reacting to
    # the same keystrokes corrupts typing -- doubled characters and duelling
    # backspace-and-retype passes -- so a named mutex lets only the first
    # instance run and later ones detect it and bow out. The name is shared by
    # the source and frozen-exe builds, so they cannot collide either.
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    handle = kernel32.CreateMutexW(None, False, "GlobalAutocorrect.SingleInstance")
    ERROR_ALREADY_EXISTS = 183
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        return None
    return handle


def main():
    global _single_instance_handle
    _single_instance_handle = acquire_single_instance_lock()
    if _single_instance_handle is None:
        print("Global autocorrect is already running; this duplicate will exit.")
        logging.warning("Refused to start: another instance already holds the lock.")
        return

    engine = (
        "windows"
        if config.get("engine", "windows") == "windows" and winspell.available()
        else "symspell"
    )
    print("Global autocorrect is running.")
    print(f"Engine: {engine}")
    print(f"Toggle: {config['hotkeys']['toggle']}")
    print(f"Exit:   {config['hotkeys']['exit']}")
    print(f"Log:    {LOG_PATH}")
    logging.info("Global autocorrect started (engine=%s)", engine)
    keyboard.on_press(on_press)
    # Reset the pending word on any mouse click, since a click moves the caret
    # and would otherwise make us backspace over unrelated text.
    mouse.on_button(reset_buffer, buttons=(mouse.LEFT, mouse.MIDDLE, mouse.RIGHT))
    keyboard.add_hotkey(config["hotkeys"]["toggle"], toggle)
    keyboard.add_hotkey(config["hotkeys"]["exit"], should_exit.set)
    should_exit.wait()
    keyboard.unhook_all()
    mouse.unhook_all()
    logging.info("Global autocorrect exited")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
