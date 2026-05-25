# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller ビルド設定ファイル
#
# 使い方:
#   .venv\Scripts\pyinstaller build.spec
#
# 生成物: dist\insta-poster\insta-poster.exe
#
# 注意:
#   - tkinterdnd2 の tkdnd ライブラリ（.dll）を同梱するために datas を使用する
#   - customtkinter のアセット（画像・テーマ）も同梱が必要
#   - APScheduler の SQLite jobstore は sqlalchemy に依存するため hiddenimports に追加

import sys
import sysconfig
from pathlib import Path

# site-packages のパスを取得（ローカル仮想環境・GitHub Actions どちらでも動く）
site_pkgs = Path(sysconfig.get_path('purelib'))

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # tkinterdnd2 の tkdnd ライブラリ（OS 別 DLL を含む）
        (str(site_pkgs / 'tkinterdnd2' / 'tkdnd'), 'tkinterdnd2/tkdnd'),
        # CustomTkinter のテーマ・画像アセット
        (str(site_pkgs / 'customtkinter'), 'customtkinter'),
    ],
    hiddenimports=[
        # APScheduler の SQLAlchemy jobstore が動的にインポートするモジュール
        'apscheduler.jobstores.sqlalchemy',
        'sqlalchemy.dialects.sqlite',
        'sqlalchemy.dialects.sqlite.pysqlite',
        # google-genai の内部モジュール
        'google.genai',
        'google.auth',
        'google.auth.transport.requests',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='insta-poster',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,      # コンソールウィンドウを非表示（GUI アプリ）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='assets/icon.ico',  # アイコンがあれば指定する
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='insta-poster',
)
