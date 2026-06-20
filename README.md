# Global Autocorrect for Windows

Aggressive phone-style autocorrect for a normal Windows hardware keyboard.

This is a small local background tool that watches typed words, then replaces obvious misspellings after you press space or punctuation. It is meant to feel closer to Microsoft Teams / mobile autocorrect, but globally across normal desktop apps.

## What It Does

- Corrects words after space or punctuation.
- Uses a local SymSpell frequency dictionary.
- Supports exact custom replacements in `global_autocorrect_config.json`.
- Starts at sign-in after installation.
- Can be paused instantly with `Ctrl+Alt+A`.
- Avoids common risky apps by default, including terminals, code editors, Python, password managers, and games.

## Install

1. Download and unzip the release.
2. Right-click `install.ps1`.
3. Choose **Run with PowerShell**.

If the release includes `GlobalAutocorrect.exe`, no Python install is needed. If the exe is not present, the installer falls back to Python 3.10+ and creates a local `.venv`.

Windows SmartScreen may warn on first launch because this is an unsigned community utility.

## Download For Users

Use `global-autocorrect-windows.zip` from the repo root or the latest release artifact. It includes:

- `GlobalAutocorrect.exe`
- the local frequency dictionary
- install/start/stop/uninstall PowerShell scripts
- editable config

No Python install is needed when using the release zip.

## Build From Source

```powershell
.\build_release.ps1
```

That creates `GlobalAutocorrect.exe` and `global-autocorrect-windows.zip`.

## Controls

- Pause/resume: `Ctrl+Alt+A`
- Exit until next launch: `Ctrl+Alt+Esc`
- Start manually: `start_global_autocorrect.ps1`
- Stop manually: `stop_global_autocorrect.ps1`
- Run visibly for debugging: `run_console.ps1`
- Uninstall startup entry: `uninstall.ps1`

## Tuning

Edit `global_autocorrect_config.json`.

Useful fields:

- `max_edit_distance`: higher means more aggressive.
- `min_word_length`: shorter means more aggressive.
- `manual_replacements`: exact typo fixes.
- `never_correct`: words to leave alone.
- `blocked_processes`: apps where autocorrect should disable itself.
- `log_corrections`: off by default for privacy.

Example:

```json
"manual_replacements": {
  "teh": "the",
  "becuase": "because",
  "youre": "you're"
}
```

Restart after editing:

```powershell
.\stop_global_autocorrect.ps1
.\start_global_autocorrect.ps1
```

## Privacy

This tool runs locally. It does not send typed text to the internet.

It does use a global keyboard hook so it can detect word boundaries and replace text. That is powerful and should be treated with care. Correction logging is disabled by default; if you turn `log_corrections` on, corrected word pairs may be written to `global_autocorrect.log`.

## Caveats

- It does not use Microsoft Teams' private autocorrect engine.
- It is a global keyboard hook that simulates backspace and typing.
- It may behave badly in some apps with custom input fields.
- It cannot reliably detect password fields, so sensitive apps are blocked by process name instead.
- It is intentionally aggressive; add false positives to `never_correct` or `manual_replacements`.

## How It Works

The loop is simple:

```text
typed word -> space/punctuation -> spell lookup -> backspace word -> type correction
```

The default engine is SymSpell with an English frequency dictionary. Exact replacements win before fuzzy dictionary guessing.
