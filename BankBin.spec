# -*- mode: python ; coding: utf-8 -*-

import os

BUILD_NAME = os.environ.get('BANKBIN_BUILD_NAME', 'BankBin')


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('bin_database.db', '.'), ('PANELS.md', '.'), ('README.md', '.'), ('代码地图.md', '.'), ('规划地图.md', '.')],
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
    a.binaries,
    a.datas,
    [],
    name=BUILD_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
