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
    if sys_os == "Windows":
        ico_path = os.path.join(base_dir, "NullifyPDF_icon.ico")
        return ico_path.replace("\\", "/") if os.path.exists(ico_path) else None
    elif sys_os == "Darwin":
        icns_path = os.path.join(base_dir, "NullifyPDF_icon.icns")
        return icns_path.replace("\\", "/") if os.path.exists(icns_path) else None
    return os.path.join(base_dir, "NullifyPDF_icon.png").replace("\\", "/")


def build_rpm(version, executable_name):
    print("\n[*] Creazione pacchetto RPM per Fedora/RHEL...")
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
                        f"dist/NullifyPDF_v{version}_Fedora.rpm",
                    )
        print("[✓] RPM creato con successo.")
    except Exception as e:
        print(f"[-] Errore RPM: {e}")
    finally:
        shutil.rmtree(rpm_dir, ignore_errors=True)


def build_deb(version, executable_name):
    print("\n[*] Creazione pacchetto DEB per Ubuntu/Debian...")
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
            ["dpkg-deb", "--build", pkg_dir, f"dist/NullifyPDF_v{version}_Ubuntu.deb"],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        print("[✓] DEB creato con successo.")
    except Exception as e:
        print(f"[-] Errore DEB: {e}")
    finally:
        shutil.rmtree(pkg_dir, ignore_errors=True)


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
        else ("macOS", "") if sys_os == "Darwin" else ("Linux_Portable", "")
    )
    final_name = f"NullifyPDF_v{version}_{os_name}{ext}"
    icon_path = ensure_icon(sys_os)
    icon_str = f"'{icon_path}'" if icon_path else "None"

    # Generazione dinamica del file .spec per supportare il nuovo standard macOS ONEDIR
    if sys_os == "Darwin":
        spec_content = f"""# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
datas = [('images', 'images')] if __import__('os').path.exists('images') else []
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
datas = [('images', 'images')] if __import__('os').path.exists('images') else []
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
            print(f"[✓] Compilazione completata: dist/{final_name}")
        elif sys_os == "Darwin":
            print("[*] Compressione App Bundle per macOS in formato ZIP...")
            # FIX PATHING ZIP: Il nome file non deve contenere 'dist/' se cwd='dist'
            zip_filename = f"NullifyPDF_v{version}_macOS.zip"
            subprocess.run(
                ["zip", "-r", "-y", zip_filename, "NullifyPDF.app"],
                cwd="dist",
                check=True,
                stdout=subprocess.DEVNULL,
            )
            shutil.rmtree("dist/NullifyPDF.app")
            print(f"[✓] Compilazione completata: dist/{zip_filename}")
        else:  # Linux
            os.rename("dist/NullifyPDF", f"dist/{final_name}")
            print(f"[✓] Eseguibile portatile pronto: dist/{final_name}")
            if shutil.which("rpmbuild"):
                build_rpm(version, final_name)
            if shutil.which("dpkg-deb"):
                build_deb(version, final_name)

    except subprocess.CalledProcessError as e:
        print(f"\n[-] ERRORE CRITICO: Compilazione fallita.")
        sys.exit(1)


if __name__ == "__main__":
    build_app()
