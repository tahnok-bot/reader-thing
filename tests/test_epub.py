from ebooklib import epub

from reader_thing.epub import build_epub


def test_build_epub_is_valid(tmp_path):
    data = build_epub("My Title", "<p>Body text here.</p>", url="http://x")
    assert data[:2] == b"PK"  # zip magic

    path = tmp_path / "book.epub"
    path.write_bytes(data)
    book = epub.read_epub(str(path))
    assert book.title == "My Title"
