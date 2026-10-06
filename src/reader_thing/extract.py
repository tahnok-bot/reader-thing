import mimetypes
import re
from html import unescape

import io
from pathlib import PurePosixPath
from urllib.parse import unquote, urlparse

import httpx
import trafilatura
from pypdf import PdfReader
from trafilatura.metadata import extract_metadata

UA = "reader-thing/0.1 (+https://github.com/)"


def fetch(url: str) -> str | bytes:
    """Return the page's HTML, or the raw bytes if the URL is a PDF."""
    r = httpx.get(
        url, follow_redirects=True, timeout=30.0, headers={"User-Agent": UA}
    )
    r.raise_for_status()
    # Some servers label PDFs application/octet-stream, so sniff too.
    if "pdf" in r.headers.get("content-type", "") or r.content.startswith(b"%PDF-"):
        return r.content
    return r.text


def pdf_title(data: bytes, url: str | None = None) -> str:
    """Title from the PDF's metadata, else its filename. Raises if not a PDF."""
    reader = PdfReader(io.BytesIO(data))
    title = ((reader.metadata or {}).get("/Title") or "").strip()
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
