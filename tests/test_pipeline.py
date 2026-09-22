from reader_thing import extract as extract_mod
from reader_thing.pipeline import process_url
from reader_thing.storage import MemoryStorage


def test_process_url(conn, sample_html, monkeypatch):
    monkeypatch.setattr(extract_mod, "fetch", lambda url: sample_html)
    storage = MemoryStorage()

    row = process_url("http://example.com/a", conn, storage)

    assert row["title"] == "Test Article"
    assert row["url"] == "http://example.com/a"
    assert storage.get(row["s3_key"])[:2] == b"PK"


def test_process_url_rejects_empty(conn, monkeypatch):
    monkeypatch.setattr(extract_mod, "fetch", lambda url: "<html><body></body></html>")
    try:
        process_url("http://example.com/empty", conn, MemoryStorage())
    except ValueError:
        return
    raise AssertionError("expected ValueError for empty content")
