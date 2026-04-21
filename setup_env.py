import os
import sys
import shutil
import subprocess
import platform


def setup_environment():
    venv_dir = ".venv"
    print("--- Inizializzazione Ambiente Virtuale Cross-Platform ---")

    # 1. Rimuove eventuali venv corrotti precedenti
    if os.path.exists(venv_dir):
        print("[*] Rimozione vecchio ambiente virtuale in corso...")
        shutil.rmtree(venv_dir, ignore_errors=True)

    # 2. Crea il nuovo venv
    print(f"[*] Creazione del nuovo ambiente virtuale ({venv_dir})...")
    try:
        subprocess.run([sys.executable, "-m", "venv", venv_dir], check=True)
    except subprocess.CalledProcessError:
        print("[-] Errore critico durante la creazione del venv.")
        sys.exit(1)

    # 3. Identifica i percorsi corretti in base al Sistema Operativo
    if platform.system() == "Windows":
        venv_python = os.path.join(venv_dir, "Scripts", "python.exe")
        activate_cmd = f".\\{venv_dir}\\Scripts\\Activate.ps1"
    else:  # macOS / Linux
        venv_python = os.path.join(venv_dir, "bin", "python")
        activate_cmd = f"source {venv_dir}/bin/activate"

    if not os.path.exists(venv_python):
        print("[-] Errore: L'eseguibile Python non è stato trovato nel nuovo ambiente.")
        sys.exit(1)

    # 4. Aggiorna pip
    print("[*] Aggiornamento di pip...")
    subprocess.run([venv_python, "-m", "pip", "install", "--upgrade", "pip", "-q"])

    # 5. Installa dipendenze base, AI e tools di build
    print(
        "[*] Installazione librerie (customtkinter, PyMuPDF, pillow, presidio-analyzer, spacy, pyinstaller)..."
    )
    subprocess.run(
        [
            venv_python,
            "-m",
            "pip",
            "install",
            "customtkinter",
            "PyMuPDF",
            "pillow",
            "presidio-analyzer",
            "spacy",
            "pyinstaller",
        ]
    )

    # 6. Download dei Modelli Linguistici AI (Inglese e Italiano)
    print(
        "[*] Download dei modelli linguistici AI (spaCy EN & IT)... attendere, potrebbe volerci un po'..."
    )
    subprocess.run([venv_python, "-m", "spacy", "download", "en_core_web_md"])
    subprocess.run([venv_python, "-m", "spacy", "download", "it_core_news_md"])

    # 7. Output finale
    print("\n" + "=" * 50)
    print("[✓] Setup Completato con Successo!")
    print("Per attivare l'ambiente e avviare NullifyPDF, usa questo comando:")
    print(f"->  {activate_cmd}")
    print("=" * 50)


if __name__ == "__main__":
    setup_environment()
