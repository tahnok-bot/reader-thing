import io

from ebooklib import epub


def build_epub(title: str, body_xhtml: str, url: str | None = None) -> bytes:
    book = epub.EpubBook()
    book.set_identifier(url or title)
    book.set_title(title)
    book.set_language("en")
    book.add_author("reader-thing")

    source = f'<p><a href="{url}">{url}</a></p>' if url else ""
    chapter = epub.EpubHtml(title=title, file_name="article.xhtml", lang="en")
    chapter.content = f"<h1>{title}</h1>{source}{body_xhtml or ''}"
    book.add_item(chapter)

    book.toc = (chapter,)
    book.spine = ["nav", chapter]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    buf = io.BytesIO()
    epub.write_epub(buf, book)
    return buf.getvalue()
