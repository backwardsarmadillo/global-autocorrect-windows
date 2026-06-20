$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$StopScript = Join-Path $ScriptDir "stop_global_autocorrect.ps1"
if (Test-Path $StopScript) {
    & $StopScript
}

$Exe = Join-Path $ScriptDir "GlobalAutocorrect.exe"
if (Test-Path $Exe) {
    Start-Process -FilePath $Exe -WindowStyle Hidden
    exit
}

$Pythonw = Join-Path $ScriptDir ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $Pythonw)) {
    $Pythonw = Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\pythonw.exe"
}
if (-not (Test-Path $Pythonw)) {
    $Pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
}
if (-not $Pythonw) {
    $Python = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
    if (-not $Python) {
        throw "Python was not found. Install Python 3.10+ from https://www.python.org/downloads/windows/"
    }
    $Pythonw = $Python
}
Start-Process -FilePath $Pythonw -ArgumentList "`"$ScriptDir\global_autocorrect.py`"" -WindowStyle Hidden
