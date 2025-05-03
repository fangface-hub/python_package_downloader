# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import copy_metadata
import shutil
import os

block_cipher = None

a = Analysis(
    ['python_package_downloader.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PythonPackageDownloader',
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
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    Tree('locales', prefix='locales'),
    Tree('help_source', prefix='help_source'),
    [('config.json', 'config.json', 'DATA'),
     ('loggingex_config.json', 'loggingex_config.json', 'DATA'),
     ('pyproject.toml', 'pyproject.toml', 'DATA'),
     ('Square44x44Logo.png', 'Square44x44Logo.png', 'DATA'),
     ('Square150x150Logo.png', 'Square150x150Logo.png', 'DATA')],
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PythonPackageDownloader',
)

# Copy files from _internal to dist root
dist_dir = os.path.join(DISTPATH, 'PythonPackageDownloader')
internal_dir = os.path.join(dist_dir, '_internal')

# Copy locales directory
src_locales = os.path.join(internal_dir, 'locales')
dst_locales = os.path.join(dist_dir, 'locales')
if os.path.exists(src_locales):
    if os.path.exists(dst_locales):
        shutil.rmtree(dst_locales)
    shutil.copytree(src_locales, dst_locales)

# Copy help_source directory
src_help = os.path.join(internal_dir, 'help_source')
dst_help = os.path.join(dist_dir, 'help_source')
if os.path.exists(src_help):
    if os.path.exists(dst_help):
        shutil.rmtree(dst_help)
    shutil.copytree(src_help, dst_help)

# Copy json files and other resources
for filename in ['config.json', 'loggingex_config.json', 'pyproject.toml', 'Square44x44Logo.png', 'Square150x150Logo.png']:
    src_file = os.path.join(internal_dir, filename)
    dst_file = os.path.join(dist_dir, filename)
    if os.path.exists(src_file):
        shutil.copy2(src_file, dst_file)
