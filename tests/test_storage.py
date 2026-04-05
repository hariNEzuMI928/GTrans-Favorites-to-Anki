import json
from pathlib import Path
import pytest
from src.utils.storage import load_ids, save_ids

def test_save_and_load_ids(tmp_path):
    test_file = tmp_path / "test_ids.json"
    test_ids = {"id1", "id2", "id3"}
    
    save_ids(test_file, test_ids)
    
    loaded_ids = load_ids(test_file)
    assert loaded_ids == test_ids
    assert isinstance(loaded_ids, set)

def test_load_ids_file_not_found(tmp_path):
    test_file = tmp_path / "non_existent.json"
    loaded_ids = load_ids(test_file)
    assert loaded_ids == set()

def test_load_ids_invalid_json(tmp_path):
    test_file = tmp_path / "invalid.json"
    test_file.write_text("invalid json")
    
    loaded_ids = load_ids(test_file)
    assert loaded_ids == set()

def test_load_ids_not_a_list(tmp_path):
    test_file = tmp_path / "not_list.json"
    test_file.write_text(json.dumps({"key": "value"}))
    
    loaded_ids = load_ids(test_file)
    assert loaded_ids == set()

def test_save_ids_creates_directory(tmp_path):
    test_dir = tmp_path / "subdir"
    test_file = test_dir / "test_ids.json"
    test_ids = ["id1"]
    
    save_ids(test_file, test_ids)
    assert test_file.exists()
    assert test_dir.is_dir()
