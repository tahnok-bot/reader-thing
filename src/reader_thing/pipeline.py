from urllib.parse import urljoin
from uuid import uuid4

from . import extract as _extract
from .db import get_article, insert_article, mark_failed, mark_ready
from .epub import build_epub, image_sources


def build(url):
    """Fetch, extract, and build an EPUB for a URL. Returns (title, epub bytes)."""
    html = _extract.fetch(url)
    title, body, lead_image = _extract.extract(html, url=url)
    if not body.strip():
        raise ValueError("no article content extracted")

    images = _fetch_images([*image_sources(body), lead_image], url)
    return title, build_epub(title, body, url, images=images, lead_image=lead_image)


def _build_and_store(url, storage, key=None):
    """The slow part: build an EPUB and upload it. Returns (title, key)."""
    title, data = build(url)
    key = key or f"epubs/{uuid4().hex}.epub"
    storage.put(key, data)
    return title, key


def _fetch_images(srcs, base_url):
    """Download what we can; an image that fails is just left out of the book."""
    images = {}
    for src in srcs:
        if not src or src in images:
            continue
        try:
            images[src] = _extract.fetch_image(urljoin(base_url, src))
        except Exception:  # noqa: BLE001 - a missing image shouldn't fail the article
            pass
    return images


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

