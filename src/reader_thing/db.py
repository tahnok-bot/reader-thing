import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    url        TEXT NOT NULL,
    title      TEXT NOT NULL,
    s3_key     TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'ready',
    error      TEXT,
    archived   INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(articles)")}
    if "error" not in cols:  # migrate databases created before the error column
        conn.execute("ALTER TABLE articles ADD COLUMN error TEXT")
    if "archived" not in cols:
        conn.execute(
            "ALTER TABLE articles ADD COLUMN archived INTEGER NOT NULL DEFAULT 0"
        )
    conn.commit()


def insert_article(conn, url, title, s3_key, status="ready") -> int:
    cur = conn.execute(
        "INSERT INTO articles (url, title, s3_key, status) VALUES (?, ?, ?, ?)",
        (url, title, s3_key, status),
    )
    conn.commit()
    return cur.lastrowid


def insert_pending(conn, url) -> int:
    """Record an article we've accepted but not yet fetched."""
    return insert_article(conn, url=url, title=url, s3_key="", status="pending")


def mark_ready(conn, article_id, title, s3_key) -> None:
    conn.execute(
        "UPDATE articles SET title = ?, s3_key = ?, status = 'ready', error = NULL "
        "WHERE id = ?",
        (title, s3_key, article_id),
    )
    conn.commit()


def mark_failed(conn, article_id, error) -> None:
    conn.execute(
        "UPDATE articles SET status = 'failed', error = ? WHERE id = ?",
        (error, article_id),
    )
    conn.commit()


def mark_pending(conn, article_id) -> None:
    conn.execute(
        "UPDATE articles SET status = 'pending', error = NULL WHERE id = ?",
        (article_id,),
    )
    conn.commit()


def set_archived(conn, article_id, archived=True) -> None:
    conn.execute(
        "UPDATE articles SET archived = ? WHERE id = ?", (int(archived), article_id)
    )
    conn.commit()


def delete_article(conn, article_id) -> None:
    conn.execute("DELETE FROM articles WHERE id = ?", (article_id,))
    conn.commit()


def get_article(conn, article_id):
    return conn.execute(
        "SELECT * FROM articles WHERE id = ?", (article_id,)
    ).fetchone()


def list_articles(conn):
    return conn.execute("SELECT * FROM articles ORDER BY id DESC").fetchall()
