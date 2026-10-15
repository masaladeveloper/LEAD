param([int]$Port = 8000, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    if (-not (Test-Path '.web-venv/Scripts/python.exe')) { throw 'Run .\setup.ps1 once before starting.' }
    if (-not (Test-Path 'frontend/dist/index.html')) { throw 'Run .\setup.ps1 to build the interface.' }
    $arguments = @('run_web.py', '--port', "$Port")
    if ($NoBrowser) { $arguments += '--no-browser' }
    & .\.web-venv\Scripts\python.exe @arguments
    if ($LASTEXITCODE -ne 0) { throw 'The local server stopped with an error. Check the messages above.' }
}
finally { Pop-Location }
