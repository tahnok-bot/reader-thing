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


def test_feed_lists_ready_articles_as_epub_links(client, conn):
    import xml.etree.ElementTree as ET

    from reader_thing.db import insert_pending

    client.post("/articles", data={"url": "http://example.com/a"})
    insert_pending(conn, "http://example.com/still-pending")

    r = client.get("/feed.xml")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/rss+xml")

    items = ET.fromstring(r.content).findall("channel/item")
    assert len(items) == 1
    link = items[0].findtext("link")
    assert link == "http://testserver/articles/1"
    assert items[0].findtext("pubDate").endswith("+0000")

    dl = client.get(link)
    assert dl.headers["content-type"] == "application/epub+zip"


def test_pdf_download_and_feed(client, sample_pdf, monkeypatch):
    import xml.etree.ElementTree as ET

    monkeypatch.setattr("reader_thing.extract.fetch", lambda url: sample_pdf)
    client.post("/articles", data={"url": "http://example.com/paper.pdf"})

    dl = client.get("/articles/1")
    assert dl.headers["content-type"] == "application/pdf"
    assert 'filename="1.pdf"' in dl.headers["content-disposition"]
    assert dl.content == sample_pdf

    item = ET.fromstring(client.get("/feed.xml").content).find("channel/item")
    assert item.findtext("title") == "A Paper About Sensors"
    assert item.find("enclosure").get("type") == "application/pdf"


def test_archive_hides_from_feed_and_moves_on_page(client):
    import xml.etree.ElementTree as ET

    client.post("/articles", data={"url": "http://example.com/a"})
    r = client.post("/articles/1/archive")
    assert r.json() == {"id": 1, "archived": True}

    assert not ET.fromstring(client.get("/feed.xml").content).findall("channel/item")
    assert "Archived (1)" in client.get("/").text

    client.post("/articles/1/unarchive")
    assert len(ET.fromstring(client.get("/feed.xml").content).findall("channel/item")) == 1
    assert "Archived" not in client.get("/").text


def test_delete_removes_row_and_object(client, storage):
    client.post("/articles", data={"url": "http://example.com/a"})
    key = client.get("/articles").json()[0]["s3_key"]

    r = client.post(
        "/articles/1/delete", headers={"Accept": "text/html"}, follow_redirects=False
    )
    assert r.status_code == 303
    assert client.get("/articles").json() == []
    assert key not in storage._items


def test_retry_failed_article(client, conn, monkeypatch):
    from reader_thing.db import get_article, insert_pending, mark_failed

    article_id = insert_pending(conn, "http://example.com/a")
    mark_failed(conn, article_id, "boom")
    page = client.get("/").text
    assert "boom" in page and f"/articles/{article_id}/retry" in page

    r = client.post(f"/articles/{article_id}/retry")
    assert r.status_code == 202
    row = get_article(conn, article_id)
    assert row["status"] == "ready"
    assert row["error"] is None


def test_retry_ready_article_conflicts(client):
    client.post("/articles", data={"url": "http://example.com/a"})
    assert client.post("/articles/1/retry").status_code == 409


def test_actions_on_missing_article_404(client):
    for action in ("retry", "archive", "unarchive", "delete"):
        assert client.post(f"/articles/999/{action}").status_code == 404
