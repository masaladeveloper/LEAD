# Muneer Lead CRM

An offline Windows lead CRM for Hyundai/IndiaMART enquiries. It stores the
master list in `%LOCALAPPDATA%\Muneer Lead CRM\lead_crm.db`, so duplicate Call
IDs are not added and weekly updates are retained between reports.

## Run the CRM

```powershell
python lead_crm_app.py
```

1. Choose **Import master report** once and select the existing IndiaMART lead
   master workbook.
2. Update remarks, customer response, relevance, deal temperature, win/lost,
   status, and next follow-up directly in the app.
3. Choose **Generate weekly report** to create an Excel report in the same
   17-column format used by the existing master.

## Build a Windows executable

```powershell
python -m pip install -r requirements.txt
.\build_exe.ps1
```

The single executable will be created at `dist\Muneer Lead CRM.exe`.
