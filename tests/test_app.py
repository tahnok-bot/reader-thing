def test_index_page(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "reader-thing" in r.text


def test_submit_returns_json_for_api_clients(client):
    r = client.post("/articles", data={"url": "http://example.com/a"})
    assert r.status_code == 202
    body = r.json()
    assert body["url"] == "http://example.com/a"
    assert body["status"] == "pending"
    assert isinstance(body["id"], int)


def test_submit_redirects_for_browsers(client):
    r = client.post(
        "/articles",
        data={"url": "http://example.com/b"},
        headers={"Accept": "text/html"},
        follow_redirects=False,
    )
    assert r.status_code == 303


def test_submit_list_and_download(client):
    r = client.post("/articles", data={"url": "http://example.com/a"})
    assert r.status_code == 202

    items = client.get("/articles").json()
    assert len(items) == 1
    assert items[0]["url"] == "http://example.com/a"

    dl = client.get(f"/articles/{items[0]['id']}")
    assert dl.status_code == 200
    assert dl.headers["content-type"] == "application/epub+zip"
    assert dl.content[:2] == b"PK"


def test_download_missing_returns_404(client):
    assert client.get("/articles/999").status_code == 404
