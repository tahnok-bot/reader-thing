import re
from html import unescape

import httpx
import trafilatura
from trafilatura.metadata import extract_metadata

UA = "reader-thing/0.1 (+https://github.com/)"


def fetch(url: str) -> str:
    r = httpx.get(
        url, follow_redirects=True, timeout=30.0, headers={"User-Agent": UA}
    )
    r.raise_for_status()
    return r.text


def extract(html: str, url: str | None = None) -> tuple[str, str]:
    """Return (title, article-body-as-xhtml)."""
    content = trafilatura.extract(
        html,
        url=url,
        output_format="html",
        include_comments=False,
        include_tables=True,
    )
    return _title(html), _body(content)


def _title(html: str) -> str:
    try:
        meta = extract_metadata(html)
        if meta and getattr(meta, "title", None):
            return meta.title
    except Exception:
        pass
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    return unescape(m.group(1)).strip() if m else "Untitled"


def _body(content: str | None) -> str:
    if not content:
        return ""
    m = re.search(r"<body[^>]*>(.*)</body>", content, re.S | re.I)
    return (m.group(1) if m else content).strip()
