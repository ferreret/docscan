# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec para DocScan Studio — Linux.

Uso:
    pyinstaller build/docscan-linux.spec

Genera dist/docscan/ con el binario principal y dependencias.
"""

import sys
from pathlib import Path

block_cipher = None

ROOT = Path(SPECPATH).parent

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "resources"), "resources"),
        (str(ROOT / "alembic"), "alembic"),
        (str(ROOT / "alembic.ini"), "."),
    ],
    hiddenimports=[
        # PySide6
        "PySide6.QtSvg",
        "PySide6.QtSvgWidgets",
        # SQLAlchemy dialects
        "sqlalchemy.dialects.sqlite",
        # Pipeline & providers (importados dinámicamente)
        "app.pipeline.steps",
        "app.pipeline.context",
        "app.pipeline.executor",
        "app.pipeline.serializer",
        "app.providers.anthropic_provider",
        "app.providers.base_provider",
        # Servicios
        "app.services.script_engine",
        "app.services.barcode_service",
        "app.services.image_pipeline",
        "app.services.ocr_service",
        "app.services.scanner_service",
        "app.services.update_service",
        "app.services.transfer_service",
        "app.services.batch_service",
        "app.services.import_service",
        "app.services.notification_service",
        "app.services.app_export_service",
        "app.services.image_lib",
        # OCR
        "rapidocr_onnxruntime",
        "pytesseract",
        # Barcode
        "pyzbar",
        "zxingcpp",
        # Image
        "cv2",
        "PIL",
        # PDF
        "fitz",
        # Config
        "pydantic_settings",
        "platformdirs",
        # HTTP
        "httpx",
        "httpcore",
        "h11",
        "anyio",
        "sniffio",
        # Crypto
        "cryptography",
        # Automation
        "watchdog",
        "apscheduler",
        # Version comparison
        "packaging",
        "packaging.version",
        # Scanner Linux
        "sane",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Windows-only
        "pytwain",
        "pywin32",
        "win32api",
        "win32com",
        "pythoncom",
        # Dev/test
        "pytest",
        "pytest_qt",
        # Unused AI
        "torch",
        "torchvision",
        "easyocr",
        # Heavy unused
        "matplotlib",
        "scipy",
        "pandas",
        "notebook",
        "IPython",
        "tkinter",
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="docscan",
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    console=False,
    icon=str(ROOT / "resources" / "icons" / "docscan.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=True,
    upx=True,
    upx_exclude=[],
    name="docscan",
)
