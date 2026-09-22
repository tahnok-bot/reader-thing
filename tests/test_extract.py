from reader_thing.extract import extract


def test_extract_title_and_body(sample_html):
    title, body = extract(sample_html, url="http://example.com/a")
    assert title == "Test Article"
    assert "Hello world" in body


def test_extract_falls_back_to_title_tag():
    html = "<html><head><title>Just A Title</title></head><body></body></html>"
    title, _ = extract(html)
    assert title == "Just A Title"
