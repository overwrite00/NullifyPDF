import os
import sys
import shutil
import subprocess
import platform
import re
import argparse
import pathlib
from typing import List, Optional, Tuple

from scripts.download_ocr_data import download_ocr_data


VALID_BUILD_VARIANTS = {"lite", "full"}
OCR_TESSDATA_FILES = ("eng.traineddata", "ita.traineddata")


def get_version_info() -> Tuple[str, str]:
    """Extract base version and optional prerelease label from NullifyPDF.py.

    Returns:
        Tuple[str, str]: Base version and optional prerelease label.
    """
    try:
        if not os.path.exists("NullifyPDF.py"):
            return "unknown", ""
        with open("NullifyPDF.py", "r", encoding="utf-8") as f:
            content = f.read()
            version_match = re.search(r'__version__\s*=\s*[\'"]([^\'"]+)[\'"]', content)
            prerelease_match = re.search(
                r'__version_prerelease__\s*=\s*[\'"]([^\'"]*)[\'"]',
                content,
            )
            if version_match:
                prerelease = prerelease_match.group(1).strip() if prerelease_match else ""
                return version_match.group(1), prerelease
    except (IOError, OSError) as e:
        print(f"[WARNING] Could not read version: {e}")
    return "unknown", ""


def get_version() -> str:
    """Return the base application version."""
    return get_version_info()[0]


def get_file_version(
    version: str, code_prerelease: str, env_beta_suffix: Optional[str]
) -> str:
    """Return the version string used in artifact filenames."""
    effective_suffix = (env_beta_suffix or code_prerelease or "").strip()
    if not effective_suffix:
        return version
    if version.endswith(f"-{effective_suffix}"):
        return version
    return f"{version}-{effective_suffix}"


def ensure_icon(sys_os: str) -> Optional[str]:
    """Find icon file for the current OS.

    Args:
        sys_os: Operating system name (Windows, Darwin, Linux).

    Returns:
        Optional[str]: Path to icon file, or None if not found (Windows).
    """
    base_dir = "images"
    if sys_os == "Windows":
        ico_path = os.path.join(base_dir, "NullifyPDF_icon.ico")
        return ico_path.replace("\\", "/") if os.path.exists(ico_path) else None
    elif sys_os == "Darwin":
        icns_path = os.path.join(base_dir, "NullifyPDF_icon.icns")
        return icns_path.replace("\\", "/") if os.path.exists(icns_path) else None
    return os.path.join(base_dir, "NullifyPDF_icon.png").replace("\\", "/")


def normalize_build_variant(value: Optional[str]) -> str:
    """Return a supported build variant name."""
    variant = (value or os.environ.get("NULLIFYPDF_BUILD_VARIANT") or "lite").lower()
    if variant not in VALID_BUILD_VARIANTS:
        allowed = ", ".join(sorted(VALID_BUILD_VARIANTS))
        raise ValueError(f"Build variant non valida: {variant}. Valori: {allowed}")
    return variant


def parse_args() -> argparse.Namespace:
    """Parse build command-line options."""
    parser = argparse.ArgumentParser(description="Build NullifyPDF with PyInstaller")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--lite", action="store_true", help="Build without bundled OCR")
    group.add_argument("--full", action="store_true", help="Build with bundled OCR data")
    return parser.parse_args()


def variant_from_args(args: argparse.Namespace) -> str:
    """Resolve build variant from CLI flags or environment."""
    if args.lite:
        return "lite"
    if args.full:
        return "full"
    return normalize_build_variant(None)


def ensure_ocr_data(download_func=download_ocr_data) -> None:
    """Ensure EN/IT OCR data is available for Full builds."""
    tessdata_dir = os.path.join("ocr", "tessdata")
    missing = [
        name for name in OCR_TESSDATA_FILES
        if not os.path.exists(os.path.join(tessdata_dir, name))
    ]
    if not missing:
        return

    missing_list = ", ".join(missing)
    print(
        "[INFO] Build Full richiesto: mancano dati OCR "
        f"({missing_list}). Download automatico da tesseract-ocr/tessdata_fast..."
    )
    download_func(pathlib.Path(tessdata_dir))
    still_missing = [
        name for name in OCR_TESSDATA_FILES
        if not os.path.exists(os.path.join(tessdata_dir, name))
    ]
    if still_missing:
        raise FileNotFoundError(
            "Download OCR incompleto. Mancano ancora: "
            f"{', '.join(still_missing)}. Usa --lite oppure controlla la rete."
        )


def pyinstaller_datas(
    build_variant: str, download_missing_ocr: bool = True
) -> List[Tuple[str, str]]:
    """Return data files/directories to include in the PyInstaller bundle."""
    datas: List[Tuple[str, str]] = []
    if os.path.exists("images"):
        datas.append(("images", "images"))
    if build_variant == "full":
        tessdata_dir = os.path.join("ocr", "tessdata")
        if download_missing_ocr:
            ensure_ocr_data()
        elif any(
            not os.path.exists(os.path.join(tessdata_dir, name))
            for name in OCR_TESSDATA_FILES
        ):
            raise FileNotFoundError(
                "Build Full richiesto, ma mancano file OCR. "
                "Usa download_missing_ocr=True oppure --lite."
            )
        for name in OCR_TESSDATA_FILES:
            source = os.path.join(tessdata_dir, name).replace("\\", "/")
            datas.append((source, "ocr/tessdata"))
    return datas


def build_rpm(
    version: str, file_version: str, executable_name: str, variant_label: str
) -> None:
    """Build RPM package for Fedora/RHEL.

    Args:
        version: Application version used for the RPM package metadata
            (must not contain hyphens, which the RPM Version tag disallows).
        file_version: Version string used for the output artifact filename
            (may include a beta suffix, e.g. "2.1.0-beta.2").
        executable_name: Name of compiled executable.
    """
    print("\n[INFO] Creazione pacchetto RPM per Fedora/RHEL...")
    rpm_dir = os.path.abspath("rpm_build_tmp")
    for d in ["BUILD", "BUILDROOT", "RPMS", "SOURCES", "SPECS", "SRPMS"]:
        os.makedirs(os.path.join(rpm_dir, d), exist_ok=True)

    icon_source = os.path.abspath("images/NullifyPDF_icon.png")
    spec_path = os.path.join(rpm_dir, "SPECS", "nullify.spec")

    with open(spec_path, "w", encoding="utf-8") as f:
        f.write(
            f"""
Name: nullify-pdf
Version: {version}
Release: 1
Summary: AI-Powered PDF Anonymization Tool
License: MIT
BuildArch: x86_64

%description
Professional forensic tool for PDF anonymization using AI.

%install
mkdir -p %{{buildroot}}/usr/bin
mkdir -p %{{buildroot}}/usr/share/applications
mkdir -p %{{buildroot}}/usr/share/icons/hicolor/256x256/apps

cp {os.path.abspath(f'dist/{executable_name}')} %{{buildroot}}/usr/bin/nullify-pdf
cp {icon_source} %{{buildroot}}/usr/share/icons/hicolor/256x256/apps/nullify-pdf.png

cat <<EOF > %{{buildroot}}/usr/share/applications/nullify-pdf.desktop
[Desktop Entry]
Name=NullifyPDF
Exec=/usr/bin/nullify-pdf
Icon=nullify-pdf
Type=Application
Categories=Utility;Security;
Terminal=false
StartupWMClass=nullify-pdf
EOF

%post
/usr/bin/update-desktop-database &> /dev/null || :
/usr/bin/gtk-update-icon-cache %{{_datadir}}/icons/hicolor &> /dev/null || :

%postun
/usr/bin/update-desktop-database &> /dev/null || :
/usr/bin/gtk-update-icon-cache %{{_datadir}}/icons/hicolor &> /dev/null || :

%files
/usr/bin/nullify-pdf
/usr/share/applications/nullify-pdf.desktop
/usr/share/icons/hicolor/256x256/apps/nullify-pdf.png
"""
        )

    try:
        subprocess.run(
            ["rpmbuild", "--define", f"_topdir {rpm_dir}", "-bb", spec_path],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        for root, _, files in os.walk(os.path.join(rpm_dir, "RPMS")):
            for file in files:
                if file.endswith(".rpm"):
                    shutil.move(
                        os.path.join(root, file),
                        f"dist/NullifyPDF_v{file_version}_Fedora_{variant_label}.rpm",
                    )
        print("[OK] RPM creato con successo.")
    except Exception as e:
        print(f"[ERROR] Errore RPM: {e}")
    finally:
        shutil.rmtree(rpm_dir, ignore_errors=True)


def build_deb(
    version: str, file_version: str, executable_name: str, variant_label: str
) -> None:
    """Build DEB package for Ubuntu/Debian.

    Args:
        version: Application version used for the DEB package metadata.
        file_version: Version string used for the output artifact filename
            (may include a beta suffix, e.g. "2.1.0-beta.2").
        executable_name: Name of compiled executable.
    """
    print("\n[INFO] Creazione pacchetto DEB per Ubuntu/Debian...")
    pkg_dir = "deb_build_tmp"
    for d in [
        "DEBIAN",
        "usr/bin",
        "usr/share/applications",
        "usr/share/icons/hicolor/256x256/apps",
    ]:
        os.makedirs(os.path.join(pkg_dir, d), exist_ok=True)

    shutil.copy(f"dist/{executable_name}", f"{pkg_dir}/usr/bin/nullify-pdf")
    os.chmod(f"{pkg_dir}/usr/bin/nullify-pdf", 0o755)

    if os.path.exists("images/NullifyPDF_icon.png"):
        shutil.copy(
            "images/NullifyPDF_icon.png",
            f"{pkg_dir}/usr/share/icons/hicolor/256x256/apps/nullify-pdf.png",
        )

    with open(
        f"{pkg_dir}/usr/share/applications/nullify-pdf.desktop", "w", encoding="utf-8"
    ) as f:
        f.write(
            "[Desktop Entry]\nName=NullifyPDF\nExec=/usr/bin/nullify-pdf\nIcon=nullify-pdf\nType=Application\nCategories=Utility;Security;\nTerminal=false\nStartupWMClass=nullify-pdf\n"
        )

    with open(f"{pkg_dir}/DEBIAN/control", "w", encoding="utf-8") as f:
        f.write(
            f"Package: nullify-pdf\nVersion: {version}\nSection: utils\nPriority: optional\nArchitecture: amd64\nMaintainer: Graziano\nDescription: AI PDF Redaction Tool\n"
        )

    postinst_content = "#!/bin/sh\nset -e\nupdate-desktop-database -q || true\ngtk-update-icon-cache -f -t /usr/share/icons/hicolor || true\n"
    with open(f"{pkg_dir}/DEBIAN/postinst", "w", newline="\n") as f:
        f.write(postinst_content)
    with open(f"{pkg_dir}/DEBIAN/postrm", "w", newline="\n") as f:
        f.write(postinst_content)
    os.chmod(f"{pkg_dir}/DEBIAN/postinst", 0o755)
    os.chmod(f"{pkg_dir}/DEBIAN/postrm", 0o755)

    try:
        subprocess.run(
            [
                "dpkg-deb",
                "--build",
                pkg_dir,
                f"dist/NullifyPDF_v{file_version}_Ubuntu_{variant_label}.deb",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        print("[OK] DEB creato con successo.")
    except Exception as e:
        print(f"[ERROR] Errore DEB: {e}")
    finally:
        shutil.rmtree(pkg_dir, ignore_errors=True)


def build_app(build_variant: Optional[str] = None) -> None:
    """Build NullifyPDF application for current OS using PyInstaller.

    Automatically generates platform-specific executables:
    - Windows: .exe standalone
    - macOS: .app bundle (zipped)
    - Linux: portable binary + .deb + .rpm packages
    """
    print("--- Avvio Compilazione NullifyPDF (PySide6) ---")
    build_variant = normalize_build_variant(build_variant)
    variant_label = build_variant.capitalize()
    version, code_prerelease = get_version_info()
    beta_suffix = os.environ.get("NULLIFYPDF_BETA_SUFFIX", "").strip()
    file_version = get_file_version(version, code_prerelease, beta_suffix)
    sys_os = platform.system()

    for item in ["build", "dist", "NullifyPDF.spec"]:
        if os.path.exists(item):
            shutil.rmtree(item) if os.path.isdir(item) else os.remove(item)

    os_name, ext = (
        ("Windows", ".exe")
        if sys_os == "Windows"
        else ("macOS", "") if sys_os == "Darwin" else ("Linux_Portable", "")
    )
    final_name = f"NullifyPDF_v{file_version}_{os_name}_{variant_label}{ext}"
    icon_path = ensure_icon(sys_os)
    # Use repr() to safely embed the path as a Python literal in the spec file.
    # Manual single-quote wrapping is unsafe for paths containing quotes/backslashes.
    icon_str = repr(icon_path) if icon_path else "None"
    datas_literal = repr(pyinstaller_datas(build_variant))
    print(f"[INFO] Variante build: {variant_label}")

    if sys_os == "Darwin":
        spec_content = f"""# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
datas = {datas_literal}
binaries = []
hiddenimports = ['spacy', 'presidio_analyzer']
for pkg in ['presidio_analyzer', 'spacy', 'en_core_web_md', 'it_core_news_md']:
    t = collect_all(pkg)
    datas += t[0]; binaries += t[1]; hiddenimports += t[2]

a = Analysis(['NullifyPDF.py'], datas=datas, hiddenimports=hiddenimports)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='NullifyPDF', debug=False, console=False, icon={icon_str})
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=True, upx_exclude=[], name='NullifyPDF')
app = BUNDLE(coll, name='NullifyPDF.app', icon={icon_str}, bundle_identifier='com.nullifypdf.forensic')
"""
    else:
        spec_content = f"""# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
datas = {datas_literal}
binaries = []
hiddenimports = ['spacy', 'presidio_analyzer']
for pkg in ['presidio_analyzer', 'spacy', 'en_core_web_md', 'it_core_news_md']:
    t = collect_all(pkg)
    datas += t[0]; binaries += t[1]; hiddenimports += t[2]

a = Analysis(['NullifyPDF.py'], datas=datas, hiddenimports=hiddenimports)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, name='NullifyPDF', debug=False, console=False, icon={icon_str})
"""

    with open("NullifyPDF.spec", "w", encoding="utf-8") as f:
        f.write(spec_content)

    try:
        subprocess.run(
            [sys.executable, "-m", "PyInstaller", "NullifyPDF.spec"], check=True
        )

        if sys_os == "Windows":
            os.rename("dist/NullifyPDF.exe", f"dist/{final_name}")
            print(f"[OK] Compilazione completata: dist/{final_name}")
        elif sys_os == "Darwin":
            print("[INFO] Compressione App Bundle per macOS in formato ZIP...")
            zip_filename = f"NullifyPDF_v{file_version}_macOS_{variant_label}.zip"
            subprocess.run(
                ["zip", "-r", "-y", zip_filename, "NullifyPDF.app"],
                cwd="dist",
                check=True,
                stdout=subprocess.DEVNULL,
            )
            shutil.rmtree("dist/NullifyPDF.app")
            print(f"[OK] Compilazione completata: dist/{zip_filename}")
        else:  # Linux
            os.rename("dist/NullifyPDF", f"dist/{final_name}")
            print(f"[OK] Eseguibile portatile pronto: dist/{final_name}")
            if shutil.which("rpmbuild"):
                build_rpm(version, file_version, final_name, variant_label)
            if shutil.which("dpkg-deb"):
                build_deb(version, file_version, final_name, variant_label)

    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] ERRORE CRITICO: Compilazione fallita (exit {e.returncode}).")
        sys.exit(1)


if __name__ == "__main__":
    build_app(variant_from_args(parse_args()))
