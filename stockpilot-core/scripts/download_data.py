"""Fetch the Online Retail II dataset into data/, verifying a checksum.

Source: UCI Machine Learning Repository, CC BY 4.0.
https://archive.ics.uci.edu/dataset/502/online+retail+ii
"""

from __future__ import annotations

import hashlib
import os
import sys
import zipfile
from pathlib import Path
from urllib.request import urlopen

DEFAULT_DATA_URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
DEFAULT_SHA256 = "572e36277c2390fbfde10664750731e0a86f55e33470d91919085f0408e67bfb"

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO_ROOT / "data"
ZIP_PATH = DATA_DIR / "online_retail_ii.zip"


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(url, timeout=120) as response, destination.open("wb") as out_file:
        while chunk := response.read(1024 * 1024):
            out_file.write(chunk)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def extract(zip_path: Path, destination_dir: Path) -> Path:
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        if len(names) != 1:
            raise RuntimeError(f"Expected exactly one file in the archive, found: {names}")
        archive.extractall(destination_dir)
        return destination_dir / names[0]


def main() -> None:
    url = os.environ.get("DATA_URL", DEFAULT_DATA_URL)
    expected_sha256 = os.environ.get("DATA_SHA256", DEFAULT_SHA256)

    if ZIP_PATH.exists() and sha256_of(ZIP_PATH) == expected_sha256:
        print(f"Already downloaded and verified: {ZIP_PATH}")
    else:
        print(f"Downloading {url} ...")
        download(url, ZIP_PATH)

        actual_sha256 = sha256_of(ZIP_PATH)
        if actual_sha256 != expected_sha256:
            ZIP_PATH.unlink()
            print(
                f"Checksum mismatch: expected {expected_sha256}, got {actual_sha256}. "
                "Removed the downloaded file.",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"Checksum verified: {actual_sha256}")

    extracted_path = extract(ZIP_PATH, DATA_DIR)
    print(f"Extracted: {extracted_path}")


if __name__ == "__main__":
    main()
