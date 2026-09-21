import sys
from pathlib import Path

from tint_sis import paths


def test_dev_mode_uses_repo_data(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    repo_data = Path(paths.__file__).resolve().parents[2] / "data"
    assert paths.default_data_dir() == repo_data
    assert paths.default_db_path() == repo_data / "tint_sis.db"


def test_frozen_mode_uses_user_folders(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setattr(paths, "_documents_dir", lambda: tmp_path / "docs")

    assert paths.app_data_dir() == tmp_path / "local" / "TINT_SIS"
    assert paths.default_data_dir() == tmp_path / "docs" / "TINT_SIS"
    assert paths.default_db_path() == tmp_path / "local" / "TINT_SIS" / "tint_sis.db"


def test_documents_dir_exists():
    assert paths._documents_dir().is_dir()
