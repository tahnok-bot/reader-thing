from reader_thing.storage import MemoryStorage


def test_memory_storage_roundtrip():
    s = MemoryStorage()
    s.put("epubs/k.epub", b"data")
    assert s.get("epubs/k.epub") == b"data"
