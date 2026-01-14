# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['images-resize-helper.py'],
    pathex=[],
    binaries=[('/opt/homebrew/bin/ffmpeg', 'bin')],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Resize JPG helper by RA-moon',
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
    icon=['AppIcon.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Resize JPG helper by RA-moon',
)
app = BUNDLE(
    coll,
    name='Resize JPG helper by RA-moon.app',
    icon='AppIcon.icns',
    bundle_identifier=None,
)
