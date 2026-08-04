"""
Beckhoff/pyads-Kompatibilitaet.

pyads 3.2.2 erwartet bei manchen TwinCAT-Installationen den alten Pfad
AdsApi\\TcAdsDll\\x64. Neuere TwinCAT-Installationen liefern die DLL jedoch
unter TwinCAT\\Common64. Diese Datei leitet nur den fehlerhaften pyads-Pfad
zur vorhandenen Beckhoff-DLL um. Es werden keine DLLs kopiert oder veraendert.
"""
from __future__ import annotations

import ctypes.util
import os
from pathlib import Path
from typing import Optional

_PATCHED = False
_ORIGINAL_ADD_DLL_DIRECTORY = None


def find_ads_dll_directory() -> Optional[Path]:
    candidates = []
    pf86 = os.environ.get("ProgramFiles(x86)", r"C:\\Program Files (x86)")
    pf = os.environ.get("ProgramFiles", r"C:\\Program Files")
    candidates.extend([
        Path(pf86) / "Beckhoff" / "TwinCAT" / "Common64",
        Path(pf) / "Beckhoff" / "TwinCAT" / "Common64",
    ])
    if (8 * __import__("struct").calcsize("P")) == 32:
        candidates = [p.with_name("Common32") for p in candidates] + candidates
    for directory in candidates:
        if (directory / "TcAdsDll.dll").exists():
            return directory
    return None


def prepare_pyads_import() -> Optional[Path]:
    """Bereitet den pyads-Import vor und gibt das echte DLL-Verzeichnis zurueck."""
    global _PATCHED, _ORIGINAL_ADD_DLL_DIRECTORY
    real_dir = find_ads_dll_directory()
    if real_dir is None:
        return None

    os.environ["PATH"] = str(real_dir) + os.pathsep + os.environ.get("PATH", "")

    if not _PATCHED and hasattr(os, "add_dll_directory"):
        _ORIGINAL_ADD_DLL_DIRECTORY = os.add_dll_directory

        def redirected_add_dll_directory(path):
            requested = str(path)
            normalized = requested.replace("/", "\\").lower()
            if ("adsapi" in normalized and "tcadsdll" in normalized and
                    normalized.endswith(("\\x64", "/x64")) and
                    not Path(requested).exists()):
                return _ORIGINAL_ADD_DLL_DIRECTORY(str(real_dir))
            return _ORIGINAL_ADD_DLL_DIRECTORY(path)

        os.add_dll_directory = redirected_add_dll_directory
        _PATCHED = True

    return real_dir
