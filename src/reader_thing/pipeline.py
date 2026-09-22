from uuid import uuid4

from . import extract as _extract
from .db import get_article, insert_article
from .epub import build_epub


def process_url(url: str, conn, storage):
    """Fetch a URL, extract the article, build an EPUB, store it, record it."""
    html = _extract.fetch(url)
    title, body = _extract.extract(html, url=url)
    if not body.strip():
        raise ValueError("no article content extracted")

    data = build_epub(title, body, url)
    key = f"epubs/{uuid4().hex}.epub"
    storage.put(key, data)

    article_id = insert_article(conn, url=url, title=title, s3_key=key)
    return get_article(conn, article_id)
