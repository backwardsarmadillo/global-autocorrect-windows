# Claude Review Handoff

This document is context for reviewing `global-autocorrect-windows`, a small Windows utility that simulates aggressive mobile/Teams-style autocorrect globally for hardware keyboards.

Repo:

```text
https://github.com/backwardsarmadillo/global-autocorrect-windows
```

Local project folder:

```text
C:\Users\yusuf\Documents\Codex\2026-05-31\windows-doesn-t-have-native-autocorrect\outputs\global-autocorrect
```

## Why This Exists

The user wanted Windows to behave more like Microsoft Teams' recent aggressive autocorrect, but globally across normal desktop apps. We investigated the Windows native settings first:

- `HKCU\Software\Microsoft\Input\Settings\EnableHwkbTextPrediction`
- `HKCU\Software\Microsoft\Input\Settings\EnableHwkbAutocorrection2`

Those were enabled, but Windows' hardware-keyboard autocorrect remains much weaker than Teams. Teams appears to use its own app-level Microsoft Editor/Editor Spellcheck layer, not a reusable global Windows service. So the practical implementation became a local global keyboard-hook utility.

## Current Architecture

Main file:

```text
global_autocorrect.py
```

Core behavior:

```text
typed word -> space/punctuation -> correction lookup -> backspace original -> type corrected word + separator
```

Important implementation points:

- Uses `keyboard` for global keyboard hooks, hotkeys, backspace, and simulated typing.
- Uses `psutil` plus Win32 `GetForegroundWindow` / `GetWindowThreadProcessId` to detect the foreground process.
- Uses `symspellpy` for fuzzy spell correction.
- Exact `manual_replacements` win before fuzzy dictionary lookup.
- `never_correct` protects specific words/acronyms.
- `blocked_processes` disables correction in risky contexts such as terminals, code editors, password managers, Python, and games.
- `log_corrections` is `false` by default for privacy.

Important scripts:

```text
install.ps1
start_global_autocorrect.ps1
stop_global_autocorrect.ps1
uninstall.ps1
build_release.ps1
```

Public download artifact:

```text
global-autocorrect-windows.zip
```

## Things I Tried / Problems I Hit

1. Native Windows autocorrect was not enough.

   The OS settings can be enabled, but they do not produce Teams-like behavior globally. This is why the project moved to a keyboard-hook approach.

2. The first Python spelling package was too timid.

   `autocorrect` missed obvious cases like `teh`, `becuase`, and `definately`, so I switched to `symspellpy`.

3. SymSpell at edit distance 2 was useful but not aggressive enough.

   The user explicitly preferred "aggressive as hell," so the public config currently uses:

   ```json
   "max_edit_distance": 3,
   "min_word_length": 3
   ```

   This intentionally causes corrections like `giu -> gnu`, `amd -> and`, and `tiw -> tip`. That is desired by the user, but it is risky for public defaults.

4. Short-word correction is the danger zone.

   During testing/logging, bad guesses included:

   ```text
   youre -> your
   giu -> gnu
   amd -> and
   tiw -> tip
   ver -> over
   appy -> apply
   ```

   I briefly raised `min_word_length` to 5, then lowered it back to 3 after the user said they preferred maximum aggression. Exact overrides were added for common intended cases such as `youre -> you're`, `thoghts -> thoughts`, and `antyhgkn -> anything`.

5. Debug logs originally recorded corrected word pairs.

   That was useful for tuning but bad as a public default. I added:

   ```json
   "log_corrections": false
   ```

   and guarded correction logging behind that flag.

6. PyInstaller onefile behavior creates a process pair.

   Running `GlobalAutocorrect.exe` can show a parent/child `GlobalAutocorrect.exe` pair. This appears to be normal PyInstaller onefile behavior. The stop script was updated to stop both by matching the executable path.

7. Rebuilding while the app is running fails.

   `build_release.ps1` originally failed with `PermissionError: [WinError 5] Access is denied` because `GlobalAutocorrect.exe` was running while PyInstaller tried to overwrite it. The build script now calls `stop_global_autocorrect.ps1` first.

8. Package zip initially omitted the exe/dictionary.

   I caught this by inspecting the zip contents. The current `build_release.ps1` includes:

   ```text
   GlobalAutocorrect.exe
   frequency_dictionary_en_82_765.txt
   ```

9. The repo was created on GitHub with an initial one-line README.

   I merged the unrelated histories and kept the real README from this project.

## Review Priorities

Please review this as a Windows global keyboard-hook utility, not just a normal Python script.

Highest-priority questions:

1. Is this safe enough for public users to run?
2. Is the privacy story honest and technically correct?
3. Can we better protect password fields or sensitive contexts?
4. Is the start/stop/install/uninstall behavior reliable?
5. Can simulated backspace/write recurse, race, or corrupt text?
6. Are the aggressive default settings too dangerous for a public release?
7. Should the repo contain `global-autocorrect-windows.zip`, or should the binary zip exist only as a GitHub Release asset?

## Files To Review First

Review in this order:

```text
global_autocorrect.py
global_autocorrect_config.json
install.ps1
start_global_autocorrect.ps1
stop_global_autocorrect.ps1
uninstall.ps1
build_release.ps1
README.md
.github/workflows/build-windows.yml
```

## Specific Code Areas To Inspect

In `global_autocorrect.py`:

- `DEFAULT_CONFIG`
- `foreground_process_name`
- `is_blocked_context`
- `build_spellchecker`
- `correction_for`
- `replace_previous_word`
- `on_press`
- `toggle`
- `main`

In PowerShell:

- Startup shortcut creation in `install.ps1`
- exe/Python fallback in `start_global_autocorrect.ps1`
- process matching in `stop_global_autocorrect.ps1`
- cleanup behavior in `uninstall.ps1`
- stop-before-build behavior in `build_release.ps1`

## Known Weaknesses / Open Design Questions

Password fields:

The tool cannot reliably detect password fields globally. It only disables itself by foreground process name. That means browser password fields are not automatically protected if the browser itself is not blocked. This is probably the biggest safety weakness.

Aggression:

`max_edit_distance = 3` and `min_word_length = 3` are intentionally aggressive. Good for the user's desired behavior, but maybe too surprising as a public default.

No tray UI:

There is no tray icon or visible status indicator. Controls are hotkey-based:

```text
Ctrl+Alt+A   pause/resume
Ctrl+Alt+Esc exit
```

No undo-last-correction:

There is no hotkey to undo the last autocorrection. This would be a high-value next feature.

No per-app UI:

Users must edit `blocked_processes` in JSON.

No context-aware language model:

The tool is word-level only. It does not use sentence context. That was discussed as a future direction but deliberately not implemented yet.

Global keyboard hook trust:

Even though this tool is local and does not transmit text, a global keyboard hook is inherently sensitive. The README says this, but please check whether the wording is clear enough.

Unsigned exe:

The PyInstaller executable is unsigned and may trigger Windows SmartScreen warnings.

## Suggested Improvements

I would strongly consider these before promoting it widely:

1. Default to a safer profile for public users.

   Maybe:

   ```json
   "max_edit_distance": 2,
   "min_word_length": 4
   ```

   and offer an "aggressive mode" config preset.

2. Add an undo-last-correction hotkey.

   Store the last correction and reverse it when the user presses something like `Ctrl+Alt+Z`.

3. Add temporary self-disable after correction.

   The existing `replacing` flag plus short sleep probably works, but verify that `keyboard.write()` cannot create event ordering weirdness across apps.

4. Improve sensitive-field protection.

   Possible approaches:

   - block browsers by default, or
   - detect focused control metadata through UI Automation, or
   - add a "hold hotkey to disable" / "disable after Ctrl+L" style mitigation, or
   - make users explicitly allowlist apps instead of blocklisting risky apps.

5. Add a tray icon.

   A visible tray icon with pause/resume and exit would make the tool feel less sketchy.

6. Move binary zip to GitHub Releases.

   The repo currently includes `global-autocorrect-windows.zip` so users can download immediately. Long-term, release assets are cleaner.

7. Add tests for `correction_for`.

   The correction logic can be tested without keyboard hooks.

8. Add a config reload hotkey.

   Right now config changes require restart.

## Current Git State At Handoff

Current main branch was pushed to:

```text
backwardsarmadillo/global-autocorrect-windows
```

Recent commits at the time this was written:

```text
65fbe74 Merge GitHub repository seed
6a61268 Ignore generated dictionary artifact
e11a167 Prepare public distribution
10317b3 Initial global autocorrect release
```

This handoff file may be an additional local change if it has not yet been pushed.

## My Overall Take

The core idea works: it gives Windows a global, aggressive autocorrect layer that feels closer to Teams/mobile typing than native Windows hardware-keyboard autocorrect.

The main concern is not whether it works. It does. The concern is that it operates in a sensitive layer of the system. Public release quality depends on conservative defaults, clear disclosures, and reliable escape hatches.

If you only change one thing before promoting it: add a safer default profile or an obvious first-run choice between "safe" and "aggressive."
