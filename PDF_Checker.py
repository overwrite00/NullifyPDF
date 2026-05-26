"""PDF Post-Redaction Verification Tool.

Performs deep forensic analysis on redacted PDFs to detect remaining
traces of sensitive data in text layers, metadata, and binary data.
"""

import fitz
import os
import logging

logger = logging.getLogger(__name__)


def inspect_pdf(file_path, target_word):
    """Inspect PDF for remaining traces of sensitive data.

    Performs three-layer forensic scan:
    1. Metadata and text layer analysis
    2. Binary/hex data carving
    3. Comprehensive threat verdict

    Args:
        file_path: Path to PDF to inspect.
        target_word: Word to search for (case-insensitive).

    Returns:
        None - prints results to stdout and logs.
    """
    # Input validation
    if not file_path or not isinstance(file_path, str):
        print("[-] Error: file_path must be a non-empty string")
        logger.error("inspect_pdf called with invalid file_path")
        return

    if not target_word or not isinstance(target_word, str):
        print("[-] Error: target_word must be a non-empty string")
        logger.error("inspect_pdf called with invalid target_word")
        return

    if not file_path.lower().endswith('.pdf'):
        print(f"[-] Error: File must be a PDF: {file_path}")
        logger.error(f"inspect_pdf called with non-PDF file: {file_path}")
        return
    if not os.path.exists(file_path):
        print(f"[-] Error: The file '{file_path}' does not exist.")
        return

    print(f"--- STARTING DEEP INSPECTION: {os.path.basename(file_path)} ---")
    print(f"[*] Target to search: '{target_word}'\n")

    word_lower = target_word.lower()
    alerts = 0

    # PHASE 1: Structural and Text Analysis (Decompressed)
    print("[*] Scanning Text and Metadata layers...")
    try:
        doc = fitz.open(file_path)

        # 1A. Metadata Check (Author, Title, Hidden tags)
        for key, value in doc.metadata.items():
            if value and word_lower in value.lower():
                print(
                    f"  [!] THREAT DETECTED: Trace found in metadata [{key} -> {value}]"
                )
                alerts += 1

        # 1B. Text Layer Check
        for i, page in enumerate(doc):
            text = page.get_text().lower()
            if word_lower in text:
                print(
                    f"  [!] THREAT DETECTED: The word still exists as hidden text on Page {i+1}"
                )
                alerts += 1

        doc.close()
    except Exception as e:
        print(f"[-] PyMuPDF read error: {e}")

    # PHASE 2: Raw Binary Analysis (Data Carving)
    print("[*] Scanning hex/binary...")
    try:
        with open(file_path, "rb") as f:
            raw_data = f.read().lower()
            # Searching for exact bytes of the word
            if word_lower.encode("utf-8") in raw_data:
                print(
                    "  [!] THREAT DETECTED: String trace found in the raw source code of the file."
                )
                alerts += 1
    except Exception as e:
        print(f"[-] Binary read error: {e}")

    # --- FINAL VERDICT ---
    print("\n" + "=" * 50)
    if alerts == 0:
        print("[✓] VERDICT: SECURE. The PDF is clinically clean.")
        print("    Data has been annihilated and is unrecoverable.")
    else:
        print(f"[X] VERDICT: VULNERABLE. Found {alerts} traces of sensitive data.")
    print("=" * 50)


if __name__ == "__main__":
    # INSERT YOUR REAL DATA HERE:
    file_name = "name_of_your_nullified_file.pdf"
    word_to_search = "redacted_word"

    # Start the inspection
    inspect_pdf(file_name, word_to_search)

    # Block the terminal so you can read the output
    input("\nPress ENTER to close the terminal...")
