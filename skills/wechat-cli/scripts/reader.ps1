$ErrorActionPreference = "Stop"
$skillDirectory = Split-Path -Parent $PSScriptRoot
$mapping = Get-Content -LiteralPath (Join-Path $skillDirectory "windows.json") -Raw | ConvertFrom-Json
$packageRoot = $mapping.package_root
& (Join-Path $packageRoot ".runtime/Scripts/python.exe") -X utf8 (Join-Path $packageRoot "windows/launch.py") reader @args
exit $LASTEXITCODE
