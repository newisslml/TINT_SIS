# -*- mode: python ; coding: utf-8 -*-
# Build: .venv\Scripts\pyinstaller packaging\tint_sis.spec --noconfirm --clean  (o scripts\build.ps1)
import re
from pathlib import Path

from PyInstaller.utils.hooks import collect_all
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

ROOT = Path(SPECPATH).parent
SRC = ROOT / "src"

version = re.search(
    r'__version__\s*=\s*"([^"]+)"', (SRC / "tint_sis" / "__init__.py").read_text(encoding="utf-8")
).group(1)
version_tuple = tuple(int(p) for p in (version.split(".") + ["0"] * 4)[:4])

datas = [(str(SRC / "tint_sis" / "app" / "ui"), "tint_sis/app/ui")]
binaries = []
hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
    "python_multipart",
    "sqlalchemy.dialects.sqlite",
]
for pkg in ("webview", "clr_loader", "pythonnet"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

icon = ROOT / "assets" / "tint_sis.ico"

version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=version_tuple, prodvers=version_tuple),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    "040904B0",
                    [
                        StringStruct("CompanyName", "TINT_SIS"),
                        StringStruct("FileDescription", "TINT_SIS"),
                        StringStruct("FileVersion", version),
                        StringStruct("InternalName", "TINT_SIS"),
                        StringStruct("OriginalFilename", "TINT_SIS.exe"),
                        StringStruct("ProductName", "TINT_SIS"),
                        StringStruct("ProductVersion", version),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(SRC)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["pandas", "numpy", "pytest", "tkinter", "matplotlib", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TINT_SIS",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(icon) if icon.exists() else None,
    version=version_info,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="TINT_SIS",
)
