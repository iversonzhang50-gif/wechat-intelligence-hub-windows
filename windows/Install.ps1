param([string]$PythonExe = "", [string]$Wheelhouse = "")
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$env:PYTHONUTF8 = "1"
$releaseRoot = Split-Path -Parent $PSScriptRoot
if ($PythonExe) {
    $pythonPath = (Resolve-Path -LiteralPath $PythonExe).Path
} else {
    $pythonPath = & py -3.12 -c "import sys; print(sys.executable)"
    if ($LASTEXITCODE -ne 0) { throw "Python 3.12 x64 is required; supply -PythonExe or install Python first." }
}
$installArgs = @((Join-Path $PSScriptRoot "install.py"))
if ($Wheelhouse) { $installArgs += @("--wheelhouse", $Wheelhouse) }
& $pythonPath -X utf8 @installArgs
exit $LASTEXITCODE
