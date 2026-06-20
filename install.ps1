$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Exe = Join-Path $ScriptDir "GlobalAutocorrect.exe"
if (-not (Test-Path $Exe)) {
    $VenvDir = Join-Path $ScriptDir ".venv"

    $Python = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
    if (-not $Python) {
        $Python = (Get-Command py.exe -ErrorAction SilentlyContinue).Source
    }
    if (-not $Python) {
        throw "Python was not found. Install Python 3.10+ from https://www.python.org/downloads/windows/ and run this installer again."
    }

    if (-not (Test-Path $VenvDir)) {
        if ((Split-Path -Leaf $Python) -ieq "py.exe") {
            & $Python -3 -m venv $VenvDir
        } else {
            & $Python -m venv $VenvDir
        }
    }

    $VenvPython = Join-Path $VenvDir "Scripts\python.exe"
    & $VenvPython -m pip install --upgrade pip
    & $VenvPython -m pip install -r (Join-Path $ScriptDir "requirements.txt")
}

$Startup = [Environment]::GetFolderPath("Startup")
$ShortcutPath = Join-Path $Startup "Global Autocorrect.lnk"
$StartScript = Join-Path $ScriptDir "start_global_autocorrect.ps1"
$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "powershell.exe"
$Shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$StartScript`""
$Shortcut.WorkingDirectory = $ScriptDir
$Shortcut.WindowStyle = 7
$Shortcut.Description = "Start Global Autocorrect"
$Shortcut.Save()

& (Join-Path $ScriptDir "stop_global_autocorrect.ps1")
& $StartScript

Write-Host "Global Autocorrect installed and started."
Write-Host "Pause/resume: Ctrl+Alt+A"
Write-Host "Exit: Ctrl+Alt+Esc"
