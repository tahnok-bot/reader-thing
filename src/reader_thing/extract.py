import mimetypes
import re
from html import unescape

import io
from pathlib import PurePosixPath
from urllib.parse import unquote, urlparse

import httpx
import trafilatura
from ebooklib import epub
from pypdf import PdfReader
from trafilatura.metadata import extract_metadata

UA = "reader-thing/0.1 (+https://github.com/)"


def fetch(url: str) -> str | bytes:
    """Return the page's HTML, or the raw bytes if the URL is a PDF or EPUB."""
    r = httpx.get(
        url, follow_redirects=True, timeout=30.0, headers={"User-Agent": UA}
    )
    r.raise_for_status()
    # Servers often label these application/octet-stream, so sniff too.
    content_type = r.headers.get("content-type", "")
    if "pdf" in content_type or "epub" in content_type or is_document(r.content):
        return r.content
    return r.text


def is_pdf(data: bytes) -> bool:
    return data.startswith(b"%PDF-")


def is_epub(data: bytes) -> bool:
    # An EPUB is a zip whose first entry is an uncompressed "mimetype" file.
    return data.startswith(b"PK\x03\x04") and b"application/epub+zip" in data[:100]


def is_document(data: bytes) -> bool:
    return is_pdf(data) or is_epub(data)


def document_title(data: bytes, url: str | None = None) -> str:
    """Title from a PDF or EPUB's metadata, else the URL's filename.

    Raises if the file can't be parsed.
    """
    if is_pdf(data):
        title = (PdfReader(io.BytesIO(data)).metadata or {}).get("/Title")
    else:
        book = epub.read_epub(io.BytesIO(data), {"ignore_ncx": True})
        title = next(iter(book.get_metadata("DC", "title")), (None,))[0]
    title = (title or "").strip()
    if title:
        return title
    name = PurePosixPath(unquote(urlparse(url or "").path)).stem
    return name or "Untitled"


def fetch_image(url: str) -> tuple[bytes, str]:
    """Return (data, media_type) for an image URL."""
    r = httpx.get(
        url, follow_redirects=True, timeout=30.0, headers={"User-Agent": UA}
    )
    r.raise_for_status()
    media_type = r.headers.get("content-type", "").split(";")[0].strip()
    if not media_type.startswith("image/"):
        media_type = mimetypes.guess_type(url.split("?")[0])[0] or ""
    if not media_type.startswith("image/"):
        raise ValueError(f"not an image: {url}")
    return r.content, media_type


def extract(html: str, url: str | None = None) -> tuple[str, str, str | None]:
    """Return (title, article-body-as-xhtml, lead-image-url)."""
    content = trafilatura.extract(
        html,
        url=url,
        output_format="html",
        include_comments=False,
        include_tables=True,
        include_formatting=True,
        include_images=True,
        include_links=True,
    )
    meta = _metadata(html)
    title = getattr(meta, "title", None) or _title_tag(html)
    image = getattr(meta, "image", None) or None
    return title, _body(content), image


def _metadata(html: str):
    try:
        return extract_metadata(html)
    except Exception:
        return None


def _title_tag(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    return unescape(m.group(1)).strip() if m else "Untitled"


def _body(content: str | None) -> str:
    if not content:
        return ""
    m = re.search(r"<body[^>]*>(.*)</body>", content, re.S | re.I)
    return (m.group(1) if m else content).strip()
