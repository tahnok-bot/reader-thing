def test_index_page(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "reader-thing" in r.text


def test_submit_list_and_download(client):
    r = client.post("/articles", data={"url": "http://example.com/a"}, follow_redirects=False)
    assert r.status_code == 303

    items = client.get("/articles").json()
    assert len(items) == 1
    assert items[0]["url"] == "http://example.com/a"

    dl = client.get(f"/articles/{items[0]['id']}")
    assert dl.status_code == 200
    assert dl.headers["content-type"] == "application/epub+zip"
    assert dl.content[:2] == b"PK"


def test_download_missing_returns_404(client):
    assert client.get("/articles/999").status_code == 404
