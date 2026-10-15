$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    python -c "import sys; assert sys.version_info >= (3, 11), 'Python 3.11 or later is required'"
    if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.11 or later.' }
    python -m PyInstaller --noconfirm --clean 'Muneer Lead CRM.spec'
    if ($LASTEXITCODE -ne 0) { throw 'The executable build failed.' }
    if (-not (Test-Path 'dist/Muneer Lead CRM.exe')) { throw 'The executable was not created. Build on Windows.' }
    Write-Host 'Created: dist\Muneer Lead CRM.exe'
}
finally {
    Pop-Location
}
