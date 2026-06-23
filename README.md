# Global Autocorrect for Windows

Aggressive phone-style autocorrect for a normal Windows hardware keyboard.

This is a small local background tool that watches typed words, then replaces obvious misspellings after you press space or punctuation. It is meant to feel closer to Microsoft Teams / mobile autocorrect, but globally across normal desktop apps.

## What It Does

- Corrects words after space or punctuation.
- Uses the **Windows spell-check engine** (the same suggestions behind the red squiggles) for candidates, and falls back to a bundled SymSpell dictionary if that API is unavailable.
- **Context-aware**: ranks candidates by the previous word, keyboard-key adjacency, and word frequency — so it picks the word you meant, not just the most common one.
- Leaves correctly spelled words alone (it only changes words Windows flags as misspelled).
- Supports exact custom replacements in `global_autocorrect_config.json`.
- Starts at sign-in after installation.
- Can be paused instantly with `Ctrl+Alt+A`.
- Avoids common risky apps by default, including terminals, code editors, Python, password managers, and games.

## Install

**Easiest (recommended):**

1. Download **`GlobalAutocorrectSetup.exe`** from the [latest release](https://github.com/backwardsarmadillo/global-autocorrect-windows/releases/latest).
2. Double-click it. Windows SmartScreen will warn that it's unsigned — click **More info → Run anyway** (this is a free community tool with no code-signing certificate).
3. Done. It installs just for your user (no admin needed), starts right away, and launches at every sign-in. Remove it any time from **Settings → Apps** or the Start Menu's *Uninstall Global Autocorrect*.

**Portable / no installer:**

1. Download `global-autocorrect-windows.zip` from the [latest release](https://github.com/backwardsarmadillo/global-autocorrect-windows/releases/latest) and unzip it.
2. Right-click `install.ps1` → **Run with PowerShell**.

Both the installer and the zip bundle `GlobalAutocorrect.exe`, so **no Python is required**. If you instead run from source, the scripts fall back to Python 3.10+ and create a local `.venv` (installing `keyboard`, `mouse`, `psutil`, `symspellpy`, `comtypes`). The Windows spell-check engine works on Windows 8 and later.

## Build From Source

```powershell
.\build_release.ps1
```

That creates `GlobalAutocorrect.exe` and `global-autocorrect-windows.zip`.

## Controls

- Pause/resume: `Ctrl+Alt+A` (a short rising beep means enabled, a lower beep means paused)
- Exit until next launch: `Ctrl+Alt+Esc`
- Start manually: `start_global_autocorrect.ps1`
- Stop manually: `stop_global_autocorrect.ps1`
- Run visibly for debugging: `run_console.ps1`
- Uninstall startup entry: `uninstall.ps1`

## Tuning

Edit `global_autocorrect_config.json`.

Useful fields:

- `engine`: `windows` (default; uses the Windows spell checker) or `symspell` (bundled dictionary only).
- `correct_capitalized`: also correct Capitalized words (sentence starts). Set `false` to leave likely proper nouns alone.
- `correct_real_words`: also correct already-valid words when context strongly disagrees (e.g. `their`/`there`). Off by default.
- `max_edit_distance`: higher means more aggressive (SymSpell fallback only).
- `min_word_length`: shorter means more aggressive.
- `manual_replacements`: exact typo fixes.
- `never_correct`: words to leave alone.
- `blocked_processes`: apps where autocorrect should disable itself.
- `idle_reset_seconds`: discard a pending word after this many seconds of no typing (set `0` to disable).
- `toggle_beep`: play a tone on pause/resume so you can hear the current state.
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
- It cannot reliably detect password fields, so sensitive apps are blocked by process name instead. Note this is by *process*, so a password typed into a **web** login form in your browser is not specifically protected. In practice that exposure is small: anything containing a digit or symbol is ignored, and a value submitted with Enter is never corrected. Still, if in doubt, pause with `Ctrl+Alt+A` before entering secrets in the browser.
- Clicking the mouse resets the pending word, so a correction will not fire across a caret you moved by clicking.
- It is intentionally aggressive; add false positives to `never_correct` or `manual_replacements`.

## How It Works

The loop:

```text
typed word -> space/punctuation -> spell-check -> rank candidates -> backspace word -> type correction
```

Candidates come from the Windows spell-check API (`ISpellChecker`) by default, or the bundled SymSpell dictionary as a fallback. They are then re-ranked by keyboard-key adjacency, the previous word (bigram context), and overall frequency. Exact entries in `manual_replacements` win before any of that, and `never_correct` words are always left alone.
