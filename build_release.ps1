$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir = Join-Path $ScriptDir ".venv"
$StopScript = Join-Path $ScriptDir "stop_global_autocorrect.ps1"

if (Test-Path $StopScript) {
    & $StopScript
}

$Python = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
if (-not $Python) {
    $Python = (Get-Command py.exe -ErrorAction SilentlyContinue).Source
}
if (-not $Python) {
    throw "Python was not found. Install Python 3.10+ from https://www.python.org/downloads/windows/"
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
& $VenvPython -m pip install pyinstaller

& $VenvPython -m PyInstaller --onefile --noconsole --name GlobalAutocorrect `
    --distpath $ScriptDir `
    --workpath (Join-Path $ScriptDir "build\pyinstaller") `
    --specpath (Join-Path $ScriptDir "build") `
    (Join-Path $ScriptDir "global_autocorrect.py") `
    -y

$DictSource = Join-Path $VenvDir "Lib\site-packages\symspellpy\frequency_dictionary_en_82_765.txt"
Copy-Item $DictSource (Join-Path $ScriptDir "frequency_dictionary_en_82_765.txt") -Force

$ZipPath = Join-Path $ScriptDir "global-autocorrect-windows.zip"
if (Test-Path $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}

$ReleaseFiles = @(
    "README.md",
    "LICENSE.txt",
    "requirements.txt",
    "GlobalAutocorrect.exe",
    "frequency_dictionary_en_82_765.txt",
    "global_autocorrect.py",
    "global_autocorrect_config.json",
    "install.ps1",
    "uninstall.ps1",
    "start_global_autocorrect.ps1",
    "stop_global_autocorrect.ps1",
    "run_console.ps1"
) | ForEach-Object { Join-Path $ScriptDir $_ }

Compress-Archive -Path $ReleaseFiles -DestinationPath $ZipPath -CompressionLevel Optimal
Write-Host "Built $ZipPath"
