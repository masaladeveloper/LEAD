$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -c "import sys; assert sys.version_info >= (3,11), 'Python 3.11 or later is required'"
        if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.11 or later.' }
        & py -3 -m venv .web-venv
    }
    else {
        & python -c "import sys; assert sys.version_info >= (3,11), 'Python 3.11 or later is required'"
        if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.11 or later.' }
        & python -m venv .web-venv
    }
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
    & .\.web-venv\Scripts\python.exe -m pip install -r requirements-web.txt
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
    if (-not (Test-Path 'frontend/dist/index.html')) {
        if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw 'Install Node.js 22 or later to build the interface.' }
        & node -e "if(Number(process.versions.node.split('.')[0]) < 22) throw new Error('Node.js 22 or later is required')"
        if ($LASTEXITCODE -ne 0) { throw 'Install Node.js 22 or later.' }
        & npm.cmd ci --prefix frontend
        if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
        & npm.cmd run build --prefix frontend
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    }
    Write-Host 'Setup complete. Run .\start.ps1 to open your lead workspace.'
}
finally { Pop-Location }
