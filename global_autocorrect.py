import ctypes
import importlib.resources
import json
import logging
import re
import sys
import threading
import time
from pathlib import Path

import keyboard
import psutil
from symspellpy import SymSpell, Verbosity


if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "global_autocorrect_config.json"
LOG_PATH = APP_DIR / "global_autocorrect.log"

DEFAULT_CONFIG = {
    "enabled": True,
    "log_corrections": False,
    "max_edit_distance": 3,
    "min_word_length": 3,
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
replacing = False
should_exit = threading.Event()


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

    if word[:1].isupper() and not word.isupper():
        return word

    suggestions = spellchecker.lookup(
        lower,
        Verbosity.CLOSEST,
        max_edit_distance=int(config["max_edit_distance"]),
        include_unknown=True,
        transfer_casing=False,
    )
    if not suggestions:
        return word

    best = suggestions[0]
    if best.distance <= 0 or best.distance > int(config["max_edit_distance"]):
        return word

    if best.term == lower:
        return word

    return apply_case(word, best.term)


def replace_previous_word(word, separator):
    global replacing
    corrected = correction_for(word)
    if corrected == word:
        return
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


def on_press(event):
    global buffer
    if replacing:
        return

    name = event.name
    if name in ("shift", "ctrl", "alt", "alt gr", "windows", "menu"):
        return

    if not enabled or is_blocked_context():
        buffer = []
        return

    if name in SEPARATORS:
        word = "".join(buffer)
        buffer = []
        if word:
            replace_previous_word(word, SEPARATORS[name])
        return

    if name == "backspace":
        if buffer:
            buffer.pop()
        return

    if name in ("enter", "tab", "esc", "delete", "up", "down", "left", "right"):
        buffer = []
        return

    if len(name) == 1 and (name.isalpha() or name == "'"):
        buffer.append(name)
        if len(buffer) > 48:
            buffer = buffer[-48:]
        return

    buffer = []


def toggle():
    global enabled, buffer
    enabled = not enabled
    buffer = []
    logging.info("Global autocorrect %s", "enabled" if enabled else "paused")
    print(f"Global autocorrect {'enabled' if enabled else 'paused'}")


def main():
    print("Global autocorrect is running.")
    print(f"Toggle: {config['hotkeys']['toggle']}")
    print(f"Exit:   {config['hotkeys']['exit']}")
    print(f"Log:    {LOG_PATH}")
    keyboard.on_press(on_press)
    keyboard.add_hotkey(config["hotkeys"]["toggle"], toggle)
    keyboard.add_hotkey(config["hotkeys"]["exit"], should_exit.set)
    should_exit.wait()
    keyboard.unhook_all()
    logging.info("Global autocorrect exited")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
