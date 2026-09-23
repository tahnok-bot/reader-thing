import io
import mimetypes
import re
from html import escape, unescape
from urllib.parse import urlsplit

from ebooklib import epub

# Kept light: KOReader lets the reader override fonts, so only set structure.
STYLE = """
h1 { font-size: 1.6em; margin: 0 0 0.3em; }
h2 { font-size: 1.3em; margin: 1.4em 0 0.4em; }
h3 { font-size: 1.1em; margin: 1.2em 0 0.3em; }
h1, h2, h3, h4 { font-weight: bold; page-break-after: avoid; }
.source { font-size: 0.8em; color: #666; margin: 0 0 1.5em; }
img { display: block; max-width: 100%; height: auto; margin: 1em auto; }
table { border-collapse: collapse; font-size: 0.85em; margin: 1em 0; }
th, td { border: 1px solid #999; padding: 0.2em 0.4em; }
pre { white-space: pre-wrap; font-size: 0.85em; }
"""

_IMG = re.compile(r"<img\b[^>]*>", re.I)
_SRC = re.compile(r'\bsrc\s*=\s*"([^"]*)"', re.I)


def image_sources(body_xhtml: str) -> list[str]:
    """The distinct image src values in an article body, in order."""
    srcs = []
    for tag in _IMG.findall(body_xhtml or ""):
        m = _SRC.search(tag)
        if m and unescape(m.group(1)) not in srcs:
            srcs.append(unescape(m.group(1)))
    return srcs


def build_epub(
    title: str,
    body_xhtml: str,
    url: str | None = None,
    images: dict[str, tuple[bytes, str]] | None = None,
    lead_image: str | None = None,
) -> bytes:
    """Build an EPUB.

    `images` maps each src in the body (and `lead_image`) to (data, media_type).
    Body images that aren't in it are dropped, since KOReader can't fetch them.
    """
    images = images or {}
    book = epub.EpubBook()
    book.set_identifier(url or title)
    book.set_title(title)
    book.set_language("en")
    book.add_author("reader-thing")

    files: dict[str, str] = {}

    def add_image(src: str, name: str, cover: bool = False) -> str:
        data, media_type = images[src]
        ext = mimetypes.guess_extension(media_type) or ""
        file_name = f"images/{name}{ext}"
        if cover:
            book.set_cover(file_name, data, create_page=False)
        else:
            book.add_item(
                epub.EpubImage(file_name=file_name, media_type=media_type, content=data)
            )
        files[src] = file_name
        return file_name

    lead = ""
    if lead_image in images:
        file_name = add_image(lead_image, "cover", cover=True)
        in_body = {_strip_query(s) for s in image_sources(body_xhtml)}
        if _strip_query(lead_image) not in in_body:
            lead = f'<img src="{file_name}" alt=""/>'

    def embed(m: re.Match) -> str:
        tag = m.group(0)
        src = _SRC.search(tag)
        src = unescape(src.group(1)) if src else None
        if src not in images:
            return ""
        file_name = files.get(src) or add_image(src, f"img{len(files)}")
        return _SRC.sub(f'src="{file_name}"', tag, count=1)

    body = _IMG.sub(embed, body_xhtml or "")

    style = epub.EpubItem(
        uid="style", file_name="style.css", media_type="text/css", content=STYLE
    )
    book.add_item(style)

    source = ""
    if url:
        host = urlsplit(url).hostname or url
        source = f'<p class="source"><a href="{escape(url)}">{escape(host)}</a></p>'
    chapter = epub.EpubHtml(title=title, file_name="article.xhtml", lang="en")
    chapter.content = f"<h1>{escape(title)}</h1>{source}{lead}{body}"
    chapter.add_item(style)
    book.add_item(chapter)

    book.toc = (chapter,)
    # The nav doc must be in the package but not the reading order; a one-entry
    # TOC page is just a blank-looking first page on the device.
    book.spine = [chapter]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    buf = io.BytesIO()
    epub.write_epub(buf, book)
    return buf.getvalue()


def _strip_query(src: str) -> str:
    return src.split("?")[0]
