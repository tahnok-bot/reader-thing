from pathlib import Path

from reader_thing.epub import image_sources
from reader_thing.extract import extract

FIXTURES = Path(__file__).parent / "fixtures"


def test_extract_title_and_body(sample_html):
    title, body, image = extract(sample_html, url="http://example.com/a")
    assert title == "Test Article"
    assert "Hello world" in body
    assert image is None


def test_extract_falls_back_to_title_tag():
    html = "<html><head><title>Just A Title</title></head><body></body></html>"
    title, _, _ = extract(html)
    assert title == "Just A Title"


def test_extract_keeps_images_and_formatting():
    html = (FIXTURES / "hackaday.html").read_text()
    url = "https://hackaday.com/2026/09/21/the-first-floating-nuclear-power-station/"
    title, body, image = extract(html, url=url)

    assert title == "The First Floating Nuclear Power Station"
    assert image.endswith("180914-A-WZ074-002.jpeg")
    assert len(image_sources(body)) == 2
    assert "<i>USS Sturgis.</i>" in body
    assert "The control room for the MH-1A" in body  # caption


def test_extract_keeps_bold_lead_ins_links_and_lists():
    html = (FIXTURES / "anthropic.html").read_text()
    _, body, image = extract(html, url="https://www.anthropic.com/claude-opus-5-5")

    assert "<strong>Performance.</strong>" in body
    assert "<strong>Safety.</strong>" in body
    assert "<h3>Pacing the frontier</h3>" in body
    assert '<a href="https://darioamodei.com/post/we-must-pace-the-frontier">' in body
    assert "<li>" in body
    assert image.endswith("-1200x630.jpg")
