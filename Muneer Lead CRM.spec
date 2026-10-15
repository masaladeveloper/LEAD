# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['lead_crm_app.py'],
    pathex=[],
    binaries=[],
    datas=[('templates/lead-master.xlsx', 'templates')],
    hiddenimports=[],
    hookspath=['packaging'],
    hooksconfig={},
    runtime_hooks=['packaging/smoke_workflows.py'],
    # Only etree is used by BeautifulSoup/openpyxl; these optional helpers are unused.
    excludes=['lxml.objectify', 'lxml.isoschematron', 'lxml.html', 'lxml.sax', 'lxml.builder'],
    noarchive=False,
    optimize=0,
)
# The app does not load Qt translation catalogs; its interface is English.
a.datas = [entry for entry in a.datas if not entry[0].endswith('.qm')]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Muneer Lead CRM',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
