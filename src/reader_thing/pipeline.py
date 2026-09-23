from uuid import uuid4

from . import extract as _extract
from .db import get_article, insert_article, mark_failed, mark_ready
from .epub import build_epub


def _build_and_store(url, storage):
    """The slow part: fetch, extract, build an EPUB, upload it. Returns (title, key)."""
    html = _extract.fetch(url)
    title, body = _extract.extract(html, url=url)
    if not body.strip():
        raise ValueError("no article content extracted")

    data = build_epub(title, body, url)
    key = f"epubs/{uuid4().hex}.epub"
    storage.put(key, data)
    return title, key


def process_url(url, conn, storage):
    """Fetch a URL and record a ready article, synchronously."""
    title, key = _build_and_store(url, storage)
    article_id = insert_article(conn, url=url, title=title, s3_key=key)
    return get_article(conn, article_id)


def process_pending(conn, storage, article_id, url):
    """Background worker: do the slow work for an already-recorded pending row."""
    try:
        title, key = _build_and_store(url, storage)
        mark_ready(conn, article_id, title, key)
    except Exception as e:  # noqa: BLE001 - record the failure instead of crashing
        mark_failed(conn, article_id, str(e))
