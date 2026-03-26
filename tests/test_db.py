from pathlib import Path

from pdf_searcher.db import (
    get_latest_saved_index,
    get_saved_indexes,
    load_index_from_db,
    save_index_to_db,
)


def test_save_and_load_index_db() -> None:
    db_path = Path(".test_indexes.db")
    if db_path.exists():
        db_path.unlink()

    payload = {
        "source": "test-source",
        "documents": [],
        "summary": {"file_count": 0, "page_count": 0, "fragment_count": 0, "unique_terms": 0},
        "terms": {},
    }

    try:
        record_id = save_index_to_db(payload, db_path, label="sample")
        loaded = load_index_from_db(db_path, record_id)
        saved = get_saved_indexes(db_path)

        assert record_id > 0
        assert loaded["source"] == "test-source"
        assert saved[0]["label"] == "sample"
        assert get_latest_saved_index(db_path)["id"] == record_id
    finally:
        if db_path.exists():
            db_path.unlink()
