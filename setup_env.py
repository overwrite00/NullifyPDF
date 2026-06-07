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


def _remove_venv(venv_dir: str) -> bool:
    """Rimuove il vecchio venv. Se bloccato, chiede all'utente di farlo manualmente.

    Args:
        venv_dir: Directory path to remove

    Returns:
        True se rimosso, False se bloccato
    """
    if not os.path.exists(venv_dir):
        return True

    try:
        shutil.rmtree(venv_dir)
        logger.info(f"✓ Vecchio venv rimosso")
        return True
    except Exception as e:
        logger.error(f"Impossibile rimuovere {venv_dir}: {e}")
        logger.error("")
        logger.error("=== SOLUZIONE ===")
        logger.error("Il venv è bloccato da un processo in esecuzione.")
        logger.error("")
        logger.error("1. Chiudi VS Code e tutti gli editor/IDE")
        logger.error("2. Chiudi tutti i terminali con il venv attivo")
        logger.error("3. Chiudi tutti i processi Python in esecuzione")
        logger.error("4. Elimina manualmente la cartella: .venv")
        logger.error("5. Riprova: python setup_env.py")
        logger.error("")
        return False


def setup_environment() -> None:
    """Initialize cross-platform virtual environment and install dependencies.

    Creates .venv directory, installs requirements.txt, and downloads spaCy
    language models for EN and IT.
    """
    venv_dir = ".venv"
    logger.info("Inizializzazione Ambiente Virtuale Cross-Platform")

    if os.path.exists(venv_dir):
        logger.info(f"Rimozione vecchio ambiente virtuale: {venv_dir}")
        if not _remove_venv(venv_dir):
            sys.exit(1)

    logger.info(f"Creazione nuovo ambiente virtuale: {venv_dir}")
    try:
        if platform.system() == "Windows":
            subprocess.run(["py", "-3.12", "-m", "venv", venv_dir], check=True)
        else:
            try:
                subprocess.run(["python3.12", "-m", "venv", venv_dir], check=True)
            except FileNotFoundError:
                logger.error("Python 3.12 non trovato. Installa Python 3.12 e riprova.")
                sys.exit(1)
    except subprocess.CalledProcessError as e:
        logger.error(f"Errore critico durante la creazione del venv: {e}")
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
    try:
        # check=True so a failed upgrade is surfaced instead of silently
        # continuing with a stale pip that may break later installs.
        subprocess.run(
            [venv_python, "-m", "pip", "install", "--upgrade", "pip", "-q"],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"Errore durante l'aggiornamento di pip: {e}")
        sys.exit(1)

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
    spacy_models = [
        "https://github.com/explosion/spacy-models/releases/download/en_core_web_md-3.8.0/en_core_web_md-3.8.0-py3-none-any.whl",
        "https://github.com/explosion/spacy-models/releases/download/it_core_news_md-3.8.0/it_core_news_md-3.8.0-py3-none-any.whl"
    ]
    try:
        for model_url in spacy_models:
            subprocess.run([venv_python, "-m", "pip", "install", model_url], check=True)
    except Exception as e:
        logger.warning(f"Errore durante il download modelli (non-critico): {e}")

    logger.info(f"Setup completato! Per attivare: {activate_cmd}")


if __name__ == "__main__":
    setup_environment()
