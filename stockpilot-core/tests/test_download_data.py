import hashlib
import zipfile
from pathlib import Path

import pytest

from scripts.download_data import extract, sha256_of


def test_sha256_of_matches_known_hash(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.txt"
    file_path.write_bytes(b"retailops")

    assert sha256_of(file_path) == hashlib.sha256(b"retailops").hexdigest()


def test_extract_single_file_archive(tmp_path: Path) -> None:
    zip_path = tmp_path / "archive.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("data.csv", "a,b\n1,2\n")

    destination_dir = tmp_path / "out"
    extracted_path = extract(zip_path, destination_dir)

    assert extracted_path == destination_dir / "data.csv"
    assert extracted_path.read_text() == "a,b\n1,2\n"


def test_extract_rejects_multi_file_archive(tmp_path: Path) -> None:
    zip_path = tmp_path / "archive.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("a.csv", "1")
        archive.writestr("b.csv", "2")

    with pytest.raises(RuntimeError, match="Expected exactly one file"):
        extract(zip_path, tmp_path / "out")
