from reader_thing.db import get_article, insert_article, list_articles


def test_insert_get_list(conn):
    aid = insert_article(conn, "http://x", "Title", "epubs/k.epub")
    row = get_article(conn, aid)
    assert row["url"] == "http://x"
    assert row["title"] == "Title"
    assert row["s3_key"] == "epubs/k.epub"
    assert row["status"] == "ready"

    rows = list_articles(conn)
    assert len(rows) == 1
    assert rows[0]["id"] == aid
