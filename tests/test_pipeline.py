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


def test_process_url_embeds_images(conn, monkeypatch):
    import io
    import zipfile
    from pathlib import Path

    html = (Path(__file__).parent / "fixtures" / "hackaday.html").read_text()
    monkeypatch.setattr(extract_mod, "fetch", lambda url: html)
    fetched = []

    def fake_image(url):
        fetched.append(url)
        if "WZ074-004" in url:
            raise RuntimeError("404")
        return b"\xff\xd8jpeg", "image/jpeg"

    monkeypatch.setattr(extract_mod, "fetch_image", fake_image)
    storage = MemoryStorage()

    row = process_url("https://hackaday.com/2026/09/21/x/", conn, storage)

    assert len(fetched) == 3  # two body images plus the og:image
    z = zipfile.ZipFile(io.BytesIO(storage.get(row["s3_key"])))
    article = z.read("EPUB/article.xhtml").decode()
    assert "EPUB/images/cover.jpg" in z.namelist()
    assert article.count("<img") == 2  # cover + the one body image that loaded
    assert "WZ074-004" not in article


def test_process_url_rejects_empty(conn, monkeypatch):
    monkeypatch.setattr(extract_mod, "fetch", lambda url: "<html><body></body></html>")
    try:
        process_url("http://example.com/empty", conn, MemoryStorage())
    except ValueError:
        return
    raise AssertionError("expected ValueError for empty content")


def test_process_pending_marks_ready(conn, sample_html, monkeypatch):
    from reader_thing.db import get_article, insert_pending
    from reader_thing.pipeline import process_pending

    monkeypatch.setattr(extract_mod, "fetch", lambda url: sample_html)
    storage = MemoryStorage()
    article_id = insert_pending(conn, "http://example.com/a")

    process_pending(conn, storage, article_id, "http://example.com/a")

    row = get_article(conn, article_id)
    assert row["status"] == "ready"
    assert row["title"] == "Test Article"
    assert storage.get(row["s3_key"])[:2] == b"PK"


def test_process_pending_records_failure(conn, monkeypatch):
    from reader_thing.db import get_article, insert_pending
    from reader_thing.pipeline import process_pending

    def boom(url):
        raise RuntimeError("fetch exploded")

    monkeypatch.setattr(extract_mod, "fetch", boom)
    article_id = insert_pending(conn, "http://example.com/bad")

    process_pending(conn, MemoryStorage(), article_id, "http://example.com/bad")

    row = get_article(conn, article_id)
    assert row["status"] == "failed"
    assert "fetch exploded" in row["error"]


def test_reprocess_overwrites_in_place(conn, sample_html, monkeypatch):
    from reader_thing.pipeline import reprocess

    monkeypatch.setattr(extract_mod, "fetch", lambda url: sample_html)
    storage = MemoryStorage()
    row = process_url("http://example.com/a", conn, storage)
    storage.put(row["s3_key"], b"old epub")

    new = reprocess(conn, storage, row["id"])

    assert new["s3_key"] == row["s3_key"]
    assert storage.get(row["s3_key"])[:2] == b"PK"


def test_reprocess_recovers_a_failed_article(conn, sample_html, monkeypatch):
    from reader_thing.db import insert_pending, mark_failed
    from reader_thing.pipeline import reprocess

    article_id = insert_pending(conn, "http://example.com/a")
    mark_failed(conn, article_id, "timed out")
    monkeypatch.setattr(extract_mod, "fetch", lambda url: sample_html)
    storage = MemoryStorage()

    row = reprocess(conn, storage, article_id)

    assert row["status"] == "ready"
    assert row["error"] is None
    assert storage.get(row["s3_key"])[:2] == b"PK"


def test_reprocess_failure_leaves_article_alone(conn, sample_html, monkeypatch):
    from reader_thing.pipeline import reprocess

    monkeypatch.setattr(extract_mod, "fetch", lambda url: sample_html)
    storage = MemoryStorage()
    row = process_url("http://example.com/a", conn, storage)
    before = storage.get(row["s3_key"])

    def boom(url):
        raise RuntimeError("site is down")

    monkeypatch.setattr(extract_mod, "fetch", boom)
    try:
        reprocess(conn, storage, row["id"])
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected the fetch error to propagate")

    from reader_thing.db import get_article

    assert get_article(conn, row["id"])["status"] == "ready"
    assert storage.get(row["s3_key"]) == before
