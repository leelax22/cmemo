# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['floating_memo.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets'), ('GUIDE.md', '.')],
    hiddenimports=['keyboard'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PyQt6.QtWebEngineWidgets', 'PyQt6.QtWebEngineCore', 'PyQt6.QtMultimedia', 
        'PyQt6.QtNetwork', 'PyQt6.QtSql', 'PyQt6.QtXml', 'PyQt6.QtTest', 
        'PyQt6.QtPdf', 'PyQt6.QtPdfWidgets', 'PyQt6.QtBluetooth', 
        'PyQt6.QtPositioning', 'PyQt6.QtPrintSupport', 'PyQt6.QtDesigner',
        'PyQt6.QtDBus', 'PyQt6.QtRemoteObjects', 'PyQt6.QtSensors',
        'PyQt6.QtSerialPort', 'PyQt6.QtTextToSpeech', 'PyQt6.QtNfc'
    ],
    noarchive=False,
    optimize=0,
)

# --- Optimization: Filter out unnecessary files ---
excluded_binaries = [
    'opengl32sw.dll',      # Qt software OpenGL (approx 20MB) - Uncheck if you need software fallback
    'Qt6Pdf.dll',          # PDF support
    'Qt6Network.dll',      # Network support
    'Qt6Svg.dll',          # SVG support
    'qwebp.dll', 'qtiff.dll', 'qjpeg.dll',  # Extra image formats
    'Qt6Qml.dll', 'Qt6Quick.dll' # Not using QML
]

def is_unnecessary(name):
    name = name.lower()
    # 1. Check excluded binaries
    if any(excl.lower() in name for excl in excluded_binaries):
        return True
    # 2. Filter translations (Keep only KR and EN)
    if name.endswith('.qm'):
        is_kr = '_ko' in name or name.startswith('qt_ko') or name.startswith('qtbase_ko')
        is_en = '_en' in name or name.startswith('qt_en') or name.startswith('qtbase_en')
        return not (is_kr or is_en)
    return False

a.binaries = [b for b in a.binaries if not is_unnecessary(b[0])]
a.datas = [d for d in a.datas if not is_unnecessary(d[0])]
# --------------------------------------------------

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CMEMO',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['cmemo.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='CMEMO',
)
