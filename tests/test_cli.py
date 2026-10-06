import pytest

from reader_thing import extract as extract_mod
from reader_thing.__main__ import _reprocess, main
from reader_thing.pipeline import process_url
from reader_thing.storage import MemoryStorage


def test_build_writes_epub_named_after_title(tmp_path, sample_html, monkeypatch):
    monkeypatch.setattr(extract_mod, "fetch", lambda url: sample_html)
    monkeypatch.chdir(tmp_path)

    assert main(["build", "http://example.com/a"]) == 0

    assert (tmp_path / "Test-Article.epub").read_bytes()[:2] == b"PK"


def test_build_to_explicit_path(tmp_path, sample_html, monkeypatch):
    monkeypatch.setattr(extract_mod, "fetch", lambda url: sample_html)
    out = tmp_path / "out.epub"

    assert main(["build", "http://example.com/a", "-o", str(out)]) == 0

    assert out.read_bytes()[:2] == b"PK"


def test_reprocess_requires_ids_or_all():
    with pytest.raises(SystemExit):
        main(["reprocess"])


def test_reprocess_all_carries_on_past_failures(conn, sample_html, monkeypatch, capsys):
    monkeypatch.setattr(extract_mod, "fetch", lambda url: sample_html)
    storage = MemoryStorage()
    good = process_url("http://example.com/good", conn, storage)
    bad = process_url("http://example.com/bad", conn, storage)

    def fetch(url):
        if "bad" in url:
            raise RuntimeError("gone")
        return sample_html

    monkeypatch.setattr(extract_mod, "fetch", fetch)

    assert _reprocess([], True, conn=conn, storage=storage) == 1

    out, err = capsys.readouterr()
    assert f"{good['id']}: Test Article" in out
    assert f"{bad['id']}: failed: gone" in err


def test_build_saves_pdfs_with_pdf_extension(tmp_path, sample_pdf, monkeypatch):
    monkeypatch.setattr(extract_mod, "fetch", lambda url: sample_pdf)
    monkeypatch.chdir(tmp_path)

    assert main(["build", "http://example.com/paper.pdf"]) == 0

    assert (tmp_path / "A-Paper-About-Sensors.pdf").read_bytes() == sample_pdf
