$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
# Match on the script's file name rather than its full path. A copy launched
# from inside the folder shows up on the command line as a relative name
# ("global_autocorrect.py"), so a full-path match would silently miss it and
# leave a zombie instance hooking the keyboard.
$ScriptName = "global_autocorrect.py"
$Processes = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" |
    Where-Object { $_.CommandLine -and $_.CommandLine -like "*$ScriptName*" }
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
