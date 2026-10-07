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


def test_migrates_archived_column():
    import sqlite3

    from reader_thing.db import init_db

    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute(
        "CREATE TABLE articles (id INTEGER PRIMARY KEY, url TEXT NOT NULL, "
        "title TEXT NOT NULL, s3_key TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'ready', "
        "created_at TEXT NOT NULL DEFAULT (datetime('now')))"
    )
    c.execute("INSERT INTO articles (url, title, s3_key) VALUES ('u', 't', 'k')")
    init_db(c)
    assert c.execute("SELECT archived FROM articles").fetchone()["archived"] == 0
