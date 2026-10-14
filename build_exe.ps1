$ErrorActionPreference = 'Stop'
python -c "import sys; assert sys.version_info >= (3, 11), 'Python 3.11 or later is required'"
if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.11 or later.' }
python -m PyInstaller --noconfirm --clean --windowed --onefile --name 'Muneer Lead CRM' --collect-all openpyxl lead_crm_app.py
if ($LASTEXITCODE -ne 0) { throw 'The executable build failed.' }
Write-Host 'Created: dist\Muneer Lead CRM.exe'
