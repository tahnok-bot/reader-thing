from reader_thing.storage import MemoryStorage


def test_memory_storage_roundtrip():
    s = MemoryStorage()
    s.put("epubs/k.epub", b"data")
    assert s.get("epubs/k.epub") == b"data"


def test_memory_storage_delete():
    s = MemoryStorage()
    s.put("epubs/k.epub", b"data")
    s.delete("epubs/k.epub")
    s.delete("epubs/k.epub")  # missing is fine, like S3
    assert "epubs/k.epub" not in s._items
