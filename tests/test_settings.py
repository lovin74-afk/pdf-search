from pathlib import Path

from app import normalize_recent_searches
from pdf_searcher.settings import load_settings, save_settings


def test_save_and_load_settings_roundtrip() -> None:
    settings_path = Path(".test_settings.json")
    if settings_path.exists():
        settings_path.unlink()

    try:
        save_settings(settings_path, {"last_folder": r"C:\pdfs"})
        loaded = load_settings(settings_path)
        assert loaded["last_folder"] == r"C:\pdfs"
    finally:
        if settings_path.exists():
            settings_path.unlink()


def test_normalize_recent_searches_removes_duplicates_and_limits_to_five() -> None:
    values = ["일비", "출장", "일비", " 식대 ", "교통", "숙박", "회의"]
    assert normalize_recent_searches(values) == ["일비", "출장", "식대", "교통", "숙박"]
