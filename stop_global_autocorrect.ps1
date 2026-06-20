$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ScriptPath = (Resolve-Path (Join-Path $ScriptDir "global_autocorrect.py")).Path
$Processes = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" |
    Where-Object { $_.CommandLine -and $_.CommandLine.Contains($ScriptPath) }
foreach ($Process in $Processes) {
    Stop-Process -Id $Process.ProcessId -Force
}

$ExePath = Join-Path $ScriptDir "GlobalAutocorrect.exe"
if (Test-Path $ExePath) {
    $ExeProcesses = Get-CimInstance Win32_Process -Filter "Name = 'GlobalAutocorrect.exe'" |
        Where-Object { $_.ExecutablePath -eq $ExePath }
    foreach ($Process in $ExeProcesses) {
        Stop-Process -Id $Process.ProcessId -Force
    }
}
