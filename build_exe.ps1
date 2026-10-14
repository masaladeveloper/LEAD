$ErrorActionPreference = 'Stop'

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'Python was not found. Install Python 3.11 or later and try again.'
}

python -m PyInstaller --noconfirm --clean --windowed --onefile --name 'Muneer Lead CRM' --collect-all openpyxl lead_crm_app.py
Write-Host 'Created: dist\Muneer Lead CRM.exe'
