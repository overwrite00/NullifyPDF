"""Virtual environment and dependency setup for NullifyPDF.

Sets up isolated Python environment with PySide6, PyMuPDF, Presidio,
spaCy models, and PyInstaller for cross-platform builds.
"""

import os
import sys
import shutil
import subprocess
import platform
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)-8s: %(message)s'
)
logger = logging.getLogger(__name__)


def setup_environment() -> None:
    """Initialize cross-platform virtual environment and install dependencies.

    Creates .venv directory, installs requirements.txt, and downloads spaCy
    language models for EN and IT.
    """
    venv_dir = ".venv"
    logger.info("Inizializzazione Ambiente Virtuale Cross-Platform")

    if os.path.exists(venv_dir):
        logger.info(f"Rimozione vecchio ambiente virtuale: {venv_dir}")
        shutil.rmtree(venv_dir, ignore_errors=True)

    logger.info(f"Creazione nuovo ambiente virtuale: {venv_dir}")
    try:
        subprocess.run([sys.executable, "-m", "venv", venv_dir], check=True)
    except subprocess.CalledProcessError:
        logger.error("Errore critico durante la creazione del venv")
        sys.exit(1)

    if platform.system() == "Windows":
        venv_python = os.path.join(venv_dir, "Scripts", "python.exe")
        activate_cmd = f".\\{venv_dir}\\Scripts\\Activate.ps1"
    else:
        venv_python = os.path.join(venv_dir, "bin", "python")
        activate_cmd = f"source {venv_dir}/bin/activate"

    if not os.path.exists(venv_python):
        logger.error("Eseguibile Python non trovato nel nuovo ambiente")
        sys.exit(1)

    logger.info("Aggiornamento pip")
    subprocess.run([venv_python, "-m", "pip", "install", "--upgrade", "pip", "-q"])

    if not os.path.exists("requirements.txt"):
        logger.error("File 'requirements.txt' non trovato nella root del progetto")
        sys.exit(1)

    logger.info("Installazione dipendenze da requirements.txt")
    try:
        subprocess.run(
            [venv_python, "-m", "pip", "install", "-r", "requirements.txt"], check=True
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"Errore durante l'installazione dipendenze: {e}")
        sys.exit(1)

    logger.info("Download modelli linguistici spaCy (EN & IT)")
    try:
        subprocess.run([venv_python, "-m", "spacy", "download", "en_core_web_md"])
        subprocess.run([venv_python, "-m", "spacy", "download", "it_core_news_md"])
    except Exception as e:
        logger.warning(f"Errore durante il download modelli (non-critico): {e}")

    logger.info(f"Setup completato! Per attivare: {activate_cmd}")


if __name__ == "__main__":
    setup_environment()
