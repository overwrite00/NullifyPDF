"""Download bundled OCR language data for NullifyPDF Full builds."""

from __future__ import annotations

import argparse
import pathlib
import urllib.request

TESSDATA_FAST_REF = "4.1.0"
LANGUAGES = ("eng", "ita")
BASE_URL = (
    "https://raw.githubusercontent.com/tesseract-ocr/"
    f"tessdata_fast/{TESSDATA_FAST_REF}"
)


def download_ocr_data(output_dir: pathlib.Path) -> None:
    """Download required Tesseract traineddata files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for lang in LANGUAGES:
        target = output_dir / f"{lang}.traineddata"
        url = f"{BASE_URL}/{lang}.traineddata"
        print(f"[INFO] Download {url}")
        urllib.request.urlretrieve(url, target)
        if target.stat().st_size < 1024:
            raise RuntimeError(f"Downloaded OCR file is unexpectedly small: {target}")
        print(f"[OK] {target}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download NullifyPDF OCR data")
    parser.add_argument(
        "--output-dir",
        default="ocr/tessdata",
        type=pathlib.Path,
        help="Destination tessdata directory",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    download_ocr_data(args.output_dir)
