# -*- mode: python ; coding: utf-8 -*-
# Build from the repository root:  pyinstaller packaging/windows/kaal-ase.spec --noconfirm
import os
from PyInstaller.utils.hooks import collect_all, copy_metadata

ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))
API = os.path.join(ROOT, "services", "api")
datas = [(os.path.join(API, "app", "static"), os.path.join("app", "static"))]
binaries = []
hidden = ["app.main", "app.launcher", "uvicorn.logging", "uvicorn.loops.auto", "uvicorn.loops.asyncio",
          "uvicorn.protocols.http.auto", "uvicorn.protocols.http.h11_impl", "uvicorn.lifespan.on", "websockets.sync.client"]
for pkg in ("maigret", "sherlock_project", "whois", "phonenumbers", "rasterio", "exifread"):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hidden += h
for dist in ("maigret", "sherlock-project", "dnspython", "python-whois", "ExifRead", "phonenumbers",
             "opencv-python-headless", "rasterio", "websockets"):
    try:
        datas += copy_metadata(dist)
    except Exception:
        pass

a = Analysis([os.path.join(SPECPATH, "entry.py")], pathex=[API], binaries=binaries, datas=datas,
             hiddenimports=hidden, excludes=["tkinter", "matplotlib", "IPython"], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="kaal-ase", console=True, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="kaal-ase")
