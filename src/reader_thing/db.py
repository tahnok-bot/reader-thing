import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    url        TEXT NOT NULL,
    title      TEXT NOT NULL,
    s3_key     TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'ready',
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
    conn.commit()


def insert_article(conn, url, title, s3_key, status="ready") -> int:
    cur = conn.execute(
        "INSERT INTO articles (url, title, s3_key, status) VALUES (?, ?, ?, ?)",
        (url, title, s3_key, status),
    )
    conn.commit()
    return cur.lastrowid


def get_article(conn, article_id):
    return conn.execute(
        "SELECT * FROM articles WHERE id = ?", (article_id,)
    ).fetchone()


def list_articles(conn):
    return conn.execute("SELECT * FROM articles ORDER BY id DESC").fetchall()
