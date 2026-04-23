import os
import sys
import shutil
import subprocess
import platform
import re


def get_version():
    """Estrae dinamicamente la versione dal file principale"""
    try:
        with open("NullifyPDF.py", "r", encoding="utf-8") as f:
            match = re.search(r'__version__\s*=\s*[\'"]([^\'"]+)[\'"]', f.read())
            if match:
                return match.group(1)
    except Exception:
        pass
    return "unknown"


def ensure_icon(sys_os):
    """Assicura che l'icona nel formato nativo corretto esista prima della compilazione"""
    base_dir = "images"
    os.makedirs(base_dir, exist_ok=True)
    png_path = os.path.join(base_dir, "NullifyPDF_icon.png")

    if sys_os == "Windows":
        ico_path = os.path.join(base_dir, "NullifyPDF_icon.ico")
        if not os.path.exists(ico_path) and os.path.exists(png_path):
            print("[*] Conversione automatica PNG -> ICO per Windows...")
            try:
                from PIL import Image

                img = Image.open(png_path)
                img.save(ico_path, format="ICO", sizes=[(256, 256)])
                return ico_path.replace("\\", "/")
            except Exception as e:
                print(f"[-] Errore generazione .ico ({e}). Icona default applicata.")
                return None
        return ico_path.replace("\\", "/") if os.path.exists(ico_path) else None

    elif sys_os == "Darwin":  # macOS
        icns_path = os.path.join(base_dir, "NullifyPDF_icon.icns")
        if not os.path.exists(icns_path) and os.path.exists(png_path):
            print("[*] Conversione automatica PNG -> ICNS per macOS...")
            try:
                from PIL import Image

                img = Image.open(png_path)
                img.save(icns_path, format="ICNS")
                return icns_path.replace("\\", "/")
            except Exception as e:
                print(f"[-] Errore generazione .icns ({e}). Icona default applicata.")
                return None
        return icns_path.replace("\\", "/") if os.path.exists(icns_path) else None

    else:  # Linux
        return png_path.replace("\\", "/") if os.path.exists(png_path) else None


def build_rpm(version, executable_name):
    print("\n[*] Rilevato sistema RPM (Fedora/RHEL). Avvio creazione .rpm nativo...")
    if not shutil.which("rpmbuild"):
        print(
            "[-] ERRORE: 'rpmbuild' non trovato. Installalo con: sudo dnf install rpm-build"
        )
        return

    rpm_dir = os.path.abspath("rpm_build_tmp")
    for d in ["BUILD", "BUILDROOT", "RPMS", "SOURCES", "SPECS", "SRPMS"]:
        os.makedirs(os.path.join(rpm_dir, d), exist_ok=True)

    spec_content = f"""Name: nullify-pdf
Version: {version}
Release: 1
Summary: AI-Powered PDF Anonymization Tool
License: MIT
Group: Applications/System

%description
Professional AI-Powered Forensic Anonymization Tool.

%install
mkdir -p %{{buildroot}}/usr/bin
mkdir -p %{{buildroot}}/usr/share/applications
mkdir -p %{{buildroot}}/usr/share/pixmaps

cp {os.path.abspath(f'dist/{executable_name}')} %{{buildroot}}/usr/bin/nullify-pdf
chmod 755 %{{buildroot}}/usr/bin/nullify-pdf

if [ -f {os.path.abspath('images/NullifyPDF_icon.png')} ]; then
    cp {os.path.abspath('images/NullifyPDF_icon.png')} %{{buildroot}}/usr/share/pixmaps/nullify-pdf.png
fi

cat <<EOF > %{{buildroot}}/usr/share/applications/nullify-pdf.desktop
[Desktop Entry]
Name=NullifyPDF
Comment=AI-Powered PDF Anonymization Tool
Exec=/usr/bin/nullify-pdf
Icon=nullify-pdf
Terminal=false
Type=Application
Categories=Utility;Security;
StartupWMClass=NullifyPDF
EOF

%files
/usr/bin/nullify-pdf
/usr/share/applications/nullify-pdf.desktop
/usr/share/pixmaps/nullify-pdf.png
"""
    spec_path = os.path.join(rpm_dir, "SPECS", "nullify.spec")
    with open(spec_path, "w", encoding="utf-8") as f:
        f.write(spec_content)

    try:
        subprocess.run(
            ["rpmbuild", "--define", f"_topdir {rpm_dir}", "-bb", spec_path],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        found = False
        for root, _, files in os.walk(os.path.join(rpm_dir, "RPMS")):
            for file in files:
                if file.endswith(".rpm"):
                    final_name = f"NullifyPDF_v{version}_Fedora.rpm"
                    shutil.move(
                        os.path.join(root, file), os.path.join("dist", final_name)
                    )
                    print(f"[✓] Creato pacchetto RPM: dist/{final_name}")
                    found = True
        if not found:
            print("[-] Impossibile trovare il file .rpm generato.")
    except Exception as e:
        print(f"[-] Errore RPM: {e}")
    finally:
        shutil.rmtree(rpm_dir, ignore_errors=True)


def build_deb(version, executable_name):
    print("\n[*] Rilevato sistema DEB (Ubuntu/Debian). Avvio creazione .deb nativo...")
    if not shutil.which("dpkg-deb"):
        print(
            "[-] ERRORE: 'dpkg-deb' non trovato. Installalo con: sudo apt-get install dpkg"
        )
        return

    pkg_dir = "deb_build_tmp"
    for d in ["DEBIAN", "usr/bin", "usr/share/applications", "usr/share/pixmaps"]:
        os.makedirs(os.path.join(pkg_dir, d), exist_ok=True)

    shutil.copy(f"dist/{executable_name}", f"{pkg_dir}/usr/bin/nullify-pdf")
    os.chmod(f"{pkg_dir}/usr/bin/nullify-pdf", 0o755)

    if os.path.exists("images/NullifyPDF_icon.png"):
        shutil.copy(
            "images/NullifyPDF_icon.png", f"{pkg_dir}/usr/share/pixmaps/nullify-pdf.png"
        )

    desktop_content = """[Desktop Entry]
Name=NullifyPDF
Comment=AI-Powered PDF Anonymization Tool
Exec=/usr/bin/nullify-pdf
Icon=nullify-pdf
Terminal=false
Type=Application
Categories=Utility;Security;
StartupWMClass=NullifyPDF
"""
    with open(
        f"{pkg_dir}/usr/share/applications/nullify-pdf.desktop", "w", encoding="utf-8"
    ) as f:
        f.write(desktop_content)

    control_content = f"""Package: nullify-pdf
Version: {version}
Section: utils
Priority: optional
Architecture: amd64
Maintainer: Graziano Mariella
Description: AI-Powered PDF Anonymization Tool
"""
    with open(f"{pkg_dir}/DEBIAN/control", "w", encoding="utf-8") as f:
        f.write(control_content)

    deb_name = f"NullifyPDF_v{version}_Ubuntu.deb"
    try:
        subprocess.run(
            ["dpkg-deb", "--build", pkg_dir, f"dist/{deb_name}"],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        print(f"[✓] Creato pacchetto DEB: dist/{deb_name}")
    except Exception as e:
        print(f"[-] Errore DEB: {e}")
    finally:
        shutil.rmtree(pkg_dir, ignore_errors=True)


def build_app():
    print("--- Avvio Compilazione Sicura di NullifyPDF ---")
    version = get_version()
    sys_os = platform.system()
    print(f"[*] Versione rilevata: v{version}")
    print(f"[*] OS Rilevato: {sys_os}")

    # Pulizia Preventiva
    for item in ["build", "dist", "NullifyPDF.spec", "deb_build_tmp", "rpm_build_tmp"]:
        if os.path.exists(item):
            shutil.rmtree(item) if os.path.isdir(item) else os.remove(item)

    if sys_os == "Windows":
        os_name, ext = "Windows", ".exe"
    elif sys_os == "Darwin":
        os_name, ext = "macOS", ".app"
    else:
        os_name, ext = "Linux_Portable", ""

    final_name = f"NullifyPDF_v{version}_{os_name}{ext}"
    icon_path = ensure_icon(sys_os)
    icon_str = f"'{icon_path}'" if icon_path else "None"

    # =========================================================================
    # MAC-OS BUNDLE SUPPORT
    # =========================================================================
    bundle_str = ""
    if sys_os == "Darwin":
        bundle_str = f"""
app = BUNDLE(
    exe,
    name='NullifyPDF.app',
    icon={icon_str},
    bundle_identifier='com.nullifypdf.forensic',
)
"""

    spec_content = f"""# -*- mode: python ; coding: utf-8 -*-
import sys
sys.setrecursionlimit(5000)

from PyInstaller.utils.hooks import collect_all

datas = [('images', 'images')] if __import__('os').path.exists('images') else []
binaries = []
hiddenimports = ['PIL._tkinter_finder', 'spacy', 'presidio_analyzer']

for pkg in ['customtkinter', 'presidio_analyzer', 'spacy', 'en_core_web_md', 'it_core_news_md']:
    tmp_ret = collect_all(pkg)
    datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

a = Analysis(
    ['NullifyPDF.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='NullifyPDF',
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
    icon={icon_str}
)
{bundle_str}
"""
    with open("NullifyPDF.spec", "w", encoding="utf-8") as spec_file:
        spec_file.write(spec_content)

    print("[*] Esecuzione PyInstaller tramite file .spec dinamico...")

    try:
        subprocess.run(
            [sys.executable, "-m", "PyInstaller", "NullifyPDF.spec"], check=True
        )
        print("\n[✓] Eseguibile standalone compilato con successo!")

        # Gestione sicura della rinomina (File su Win/Linux vs Directory .app su Mac)
        if sys_os == "Darwin":
            original_path = os.path.join("dist", "NullifyPDF.app")
        elif sys_os == "Windows":
            original_path = os.path.join("dist", "NullifyPDF.exe")
        else:
            original_path = os.path.join("dist", "NullifyPDF")

        final_path = os.path.join("dist", final_name)

        if os.path.exists(original_path):
            if os.path.exists(final_path):
                (
                    shutil.rmtree(final_path)
                    if os.path.isdir(final_path)
                    else os.remove(final_path)
                )
            os.rename(original_path, final_path)
            print(f"[✓] App rinominata correttamente: dist/{final_name}")

        # GESTIONE PACCHETTI LINUX
        if sys_os == "Linux":
            is_fedora, is_ubuntu = False, False
            try:
                with open("/etc/os-release") as f:
                    os_data = f.read().lower()
                    if "fedora" in os_data or "centos" in os_data or "rhel" in os_data:
                        is_fedora = True
                    elif "ubuntu" in os_data or "debian" in os_data:
                        is_ubuntu = True
            except:
                pass

            if is_fedora:
                build_rpm(version, final_name)
            elif is_ubuntu:
                build_deb(version, final_name)
            else:
                if shutil.which("rpmbuild"):
                    build_rpm(version, final_name)
                elif shutil.which("dpkg-deb"):
                    build_deb(version, final_name)
                else:
                    print(
                        "\n[-] Gestore pacchetti non riconosciuto. Usa l'eseguibile portatile generato."
                    )

        print("\n" + "=" * 50)
        print("[✓] Processo di Build Concluso con Successo!")
        print("Controlla la cartella 'dist/' per i tuoi file.")
        print("=" * 50)

    except subprocess.CalledProcessError:
        print("\n[-] ERRORE CRITICO: La compilazione con PyInstaller è fallita.")
        sys.exit(1)


if __name__ == "__main__":
    build_app()
