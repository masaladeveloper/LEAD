"""Package a ready-built local website, without customer data or development tools."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parent
FILES = ['README.md', 'setup.ps1', 'start.ps1', 'run_web.py', 'web_app.py', 'requirements-web.txt',
         'config.py', 'crm_database.py', 'thunderbird_sync.py', 'html_parser.py', 'mailbox_reader.py',
         'thread_parser.py', 'models.py', 'report_generator.py', 'report_service.py', 'import_service.py',
         'templates/lead-master.xlsx']


def main():
    if not (ROOT / 'frontend/dist/index.html').is_file():
        raise SystemExit('Run npm run build --prefix frontend first.')
    target = ROOT / 'dist/Muneer-Lead-Workspace.zip'
    target.parent.mkdir(exist_ok=True)
    with ZipFile(target, 'w', ZIP_DEFLATED) as archive:
        for file in [*(ROOT / name for name in FILES), *(ROOT / 'frontend/dist').rglob('*')]:
            if file.is_file():
                archive.write(file, 'Muneer-Lead-Workspace/' + file.relative_to(ROOT).as_posix())
    print(f'{target.name}: {target.stat().st_size / 1024:.0f} KiB. Python dependencies install during setup.')


if __name__ == '__main__':
    main()
