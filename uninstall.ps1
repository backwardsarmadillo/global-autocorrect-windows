$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

& (Join-Path $ScriptDir "stop_global_autocorrect.ps1")

$Startup = [Environment]::GetFolderPath("Startup")
$ShortcutPath = Join-Path $Startup "Global Autocorrect.lnk"
if (Test-Path $ShortcutPath) {
    Remove-Item -LiteralPath $ShortcutPath -Force
}

Write-Host "Global Autocorrect stopped and removed from startup."
