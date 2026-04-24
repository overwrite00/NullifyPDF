import os
import sys
import shutil
import subprocess
import platform
import re


def get_version():
    try:
        with open("NullifyPDF.py", "r", encoding="utf-8") as f:
            match = re.search(r'__version__\s*=\s*[\'"]([^\'"]+)[\'"]', f.read())
            if match:
                return match.group(1)
    except:
        pass
    return "unknown"


def ensure_icon(sys_os):
    base_dir = "images"
    os.makedirs(base_dir, exist_ok=True)
    png_path = os.path.join(base_dir, "NullifyPDF_icon.png")

    if sys_os == "Windows":
        ico_path = os.path.join(base_dir, "NullifyPDF_icon.ico")
        if not os.path.exists(ico_path) and os.path.exists(png_path):
            try:
                from PIL import Image

                img = Image.open(png_path)
                img.save(ico_path, format="ICO", sizes=[(256, 256)])
                return ico_path.replace("\\", "/")
            except:
                return None
        return ico_path.replace("\\", "/") if os.path.exists(ico_path) else None

    elif sys_os == "Darwin":
        icns_path = os.path.join(base_dir, "NullifyPDF_icon.icns")
        if not os.path.exists(icns_path) and os.path.exists(png_path):
            try:
                from PIL import Image

                img = Image.open(png_path)
                img.save(icns_path, format="ICNS")
                return icns_path.replace("\\", "/")
            except:
                return None
        return icns_path.replace("\\", "/") if os.path.exists(icns_path) else None

    return png_path.replace("\\", "/") if os.path.exists(png_path) else None


def build_app():
    print("--- Avvio Compilazione NullifyPDF (PySide6) ---")
    version = get_version()
    sys_os = platform.system()

    for item in ["build", "dist", "NullifyPDF.spec"]:
        if os.path.exists(item):
            shutil.rmtree(item) if os.path.isdir(item) else os.remove(item)

    os_name, ext = (
        ("Windows", ".exe")
        if sys_os == "Windows"
        else ("macOS", ".app") if sys_os == "Darwin" else ("Linux", "")
    )
    final_name = f"NullifyPDF_v{version}_{os_name}{ext}"
    icon_path = ensure_icon(sys_os)
    icon_str = f"'{icon_path}'" if icon_path else "None"

    bundle_str = (
        f"app = BUNDLE(exe, name='NullifyPDF.app', icon={icon_str}, bundle_identifier='com.nullifypdf.forensic',)"
        if sys_os == "Darwin"
        else ""
    )

    spec_content = f"""# -*- mode: python ; coding: utf-8 -*-
import sys
sys.setrecursionlimit(5000)
from PyInstaller.utils.hooks import collect_all

datas = [('images', 'images')] if __import__('os').path.exists('images') else []
binaries = []
hiddenimports = ['spacy', 'presidio_analyzer']

for pkg in ['presidio_analyzer', 'spacy', 'en_core_web_md', 'it_core_news_md']:
    tmp_ret = collect_all(pkg)
    datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

a = Analysis(['NullifyPDF.py'], pathex=[], binaries=binaries, datas=datas, hiddenimports=hiddenimports,
    hookspath=[], hooksconfig={{}}, runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='NullifyPDF', debug=False,
    bootloader_ignore_signals=False, strip=False, upx=True, upx_exclude=[], runtime_tmpdir=None,
    console=False, disable_windowed_traceback=False, argv_emulation=False, target_arch=None,
    codesign_identity=None, entitlements_file=None, icon={icon_str})
{bundle_str}
"""
    with open("NullifyPDF.spec", "w", encoding="utf-8") as f:
        f.write(spec_content)
    try:
        subprocess.run(
            [sys.executable, "-m", "PyInstaller", "NullifyPDF.spec"], check=True
        )

        # Rinominazione sicura basata sull'output di PyInstaller
        original_path = os.path.join(
            "dist",
            (
                "NullifyPDF.app"
                if sys_os == "Darwin"
                else "NullifyPDF.exe" if sys_os == "Windows" else "NullifyPDF"
            ),
        )
        final_path = os.path.join("dist", final_name)

        if os.path.exists(original_path):
            os.rename(original_path, final_path)
            print(f"[✓] Compilazione completata: dist/{final_name}")
        else:
            print(
                f"[-] Attenzione: File originale {original_path} non trovato in dist/"
            )
    except subprocess.CalledProcessError:
        print("\n[-] ERRORE CRITICO: Compilazione PyInstaller fallita.")
        sys.exit(1)


if __name__ == "__main__":
    build_app()
