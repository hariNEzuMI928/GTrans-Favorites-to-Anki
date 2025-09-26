import json
from pathlib import Path
import pytest

# src ディレクトリをパスに追加して、src.storage をインポートできるようにする
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.storage import load_ids, save_ids


def test_save_and_load_ids(tmp_path: Path):
    """
    Test saving a set of IDs to a file and then loading them back.
    """
    file_path = tmp_path / "processed_ids.json"
    test_ids = {"id1", "id2", "id3"}

    # 1. Test saving
    save_ids(file_path, test_ids)

    # Verify the file was created and contains the correct data
    assert file_path.exists()
    with file_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
        assert sorted(data) == sorted(list(test_ids))

    # 2. Test loading
    loaded_ids = load_ids(file_path)
    assert loaded_ids == test_ids


def test_load_ids_non_existent_file(tmp_path: Path):
    """
    Test that loading from a non-existent file returns an empty set.
    """
    file_path = tmp_path / "non_existent.json"
    assert not file_path.exists()
    loaded_ids = load_ids(file_path)
    assert loaded_ids == set()


def test_load_ids_invalid_json(tmp_path: Path):
    """
    Test that loading from a file with invalid JSON returns an empty set.
    """
    file_path = tmp_path / "invalid.json"
    file_path.write_text("this is not json", encoding="utf-8")

    loaded_ids = load_ids(file_path)
    assert loaded_ids == set()

def test_save_ids_empty_set(tmp_path: Path):
    """
    Test saving an empty set of IDs.
    """
    file_path = tmp_path / "empty_ids.json"
    save_ids(file_path, set())

    assert file_path.exists()
    loaded_ids = load_ids(file_path)
    assert loaded_ids == set()

def test_save_ids_creates_directory(tmp_path: Path):
    """
    Test that save_ids creates the parent directory if it doesn't exist.
    """
    dir_path = tmp_path / "new_dir"
    file_path = dir_path / "processed_ids.json"

    assert not dir_path.exists() # Directory should not exist initially

    save_ids(file_path, {"id1"})

    assert dir_path.exists()
    assert file_path.exists()
