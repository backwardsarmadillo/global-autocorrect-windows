$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ScriptDir ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python.exe"
}
& $Python (Join-Path $ScriptDir "global_autocorrect.py")
