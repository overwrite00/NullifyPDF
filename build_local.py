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
    except:
        pass
    return "unknown"


def build_rpm(version, executable_name):
    """Crea pacchetto RPM nativo per Fedora/RHEL"""
    print("\n[*] Rilevato sistema basato su RPM (Fedora/RHEL).")
    print("[*] Avvio creazione pacchetto .rpm nativo...")

    if not shutil.which("rpmbuild"):
        print("[-] ERRORE: 'rpmbuild' non trovato.")
        print("    -> Installalo eseguendo nel terminale: sudo dnf install rpm-build")
        return

    rpm_dir = os.path.abspath("rpm_build_tmp")
    for d in ["BUILD", "BUILDROOT", "RPMS", "SOURCES", "SPECS", "SRPMS"]:
        os.makedirs(os.path.join(rpm_dir, d), exist_ok=True)

    # File SPEC nativo. Usiamo executable_name per trovare il file rinominato
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
                    print(f"[✓] Creato pacchetto RPM installabile: dist/{final_name}")
                    found = True
        if not found:
            print("[-] Impossibile trovare il file .rpm generato.")
    except subprocess.CalledProcessError as e:
        print(f"[-] Errore durante la pacchettizzazione RPM: {e}")
    finally:
        shutil.rmtree(rpm_dir, ignore_errors=True)


def build_deb(version, executable_name):
    """Crea pacchetto DEB nativo per Ubuntu/Debian"""
    print("\n[*] Rilevato sistema basato su DEB (Ubuntu/Debian).")
    print("[*] Avvio creazione pacchetto .deb nativo...")

    if not shutil.which("dpkg-deb"):
        print("[-] ERRORE: 'dpkg-deb' non trovato.")
        print("    -> Installalo eseguendo nel terminale: sudo apt-get install dpkg")
        return

    pkg_dir = "deb_build_tmp"
    for d in ["DEBIAN", "usr/bin", "usr/share/applications", "usr/share/pixmaps"]:
        os.makedirs(os.path.join(pkg_dir, d), exist_ok=True)

    # Usa executable_name per trovare il file rinominato
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
        print(f"[✓] Creato pacchetto DEB installabile: dist/{deb_name}")
    except subprocess.CalledProcessError as e:
        print(f"[-] Errore durante la pacchettizzazione DEB: {e}")
    finally:
        shutil.rmtree(pkg_dir, ignore_errors=True)


def build_app():
    print("--- Avvio Compilazione Locale di NullifyPDF ---")
    version = get_version()
    print(f"[*] Versione rilevata: v{version}")

    # Pulizia
    for item in ["build", "dist", "NullifyPDF.spec", "deb_build_tmp", "rpm_build_tmp"]:
        if os.path.exists(item):
            shutil.rmtree(item) if os.path.isdir(item) else os.remove(item)

    sys_os = platform.system()
    separator = ";" if sys_os == "Windows" else ":"
    icon_ext = "ico" if sys_os == "Windows" else "png"

    if sys_os == "Windows":
        os_name, ext = "Windows", ".exe"
    elif sys_os == "Darwin":
        os_name, ext = "macOS", ""
    else:
        os_name, ext = "Linux_Portable", ""

    final_name = f"NullifyPDF_v{version}_{os_name}{ext}"
    print(
        f"[*] Rilevato sistema: {sys_os} -> Costruzione Eseguibile Base: {final_name}"
    )

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconsole",
        "--onefile",
        "--hidden-import",
        "PIL._tkinter_finder",
        "--collect-all",
        "customtkinter",
        "--collect-all",
        "presidio_analyzer",
        "--collect-all",
        "spacy",
        "--collect-all",
        "en_core_web_md",
        "--collect-all",
        "it_core_news_md",
        "--add-data",
        f"images{separator}images",
        "--icon",
        f"images/NullifyPDF_icon.{icon_ext}",
        "--name",
        "NullifyPDF",
        "NullifyPDF.py",
    ]

    try:
        subprocess.run(cmd, check=True)
        print("\n[✓] Eseguibile standalone compilato con successo!")

        base_ext = ".exe" if sys_os == "Windows" else ""
        original_path = os.path.join("dist", f"NullifyPDF{base_ext}")
        final_path = os.path.join("dist", final_name)

        if os.path.exists(original_path):
            os.rename(original_path, final_path)
            print(f"[✓] Eseguibile portatile rinominato: dist/{final_name}")

        # --- RILEVAMENTO OS LINUX E PACCHETTIZZAZIONE NATIVA ---
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
                # Fallback se os-release non è chiaro
                if shutil.which("rpmbuild"):
                    build_rpm(version, final_name)
                elif shutil.which("dpkg-deb"):
                    build_deb(version, final_name)
                else:
                    print(
                        "\n[-] Gestore pacchetti non riconosciuto. Usa l'eseguibile portatile Linux generato."
                    )

        print("\n" + "=" * 50)
        print("[✓] Processo di Build Locale Concluso!")
        print("Controlla la cartella 'dist/' per i tuoi file pronti all'uso.")
        print("=" * 50)

    except subprocess.CalledProcessError:
        print("\n[-] ERRORE: La compilazione con PyInstaller è fallita.")
        sys.exit(1)


if __name__ == "__main__":
    build_app()
