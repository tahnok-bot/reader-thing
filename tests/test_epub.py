import io
import zipfile

from ebooklib import epub

from reader_thing.epub import build_epub

JPEG = (b"\xff\xd8\xff\xe0jpeg bytes", "image/jpeg")
PNG = (b"\x89PNG png bytes", "image/png")


def _article(data: bytes) -> str:
    return zipfile.ZipFile(io.BytesIO(data)).read("EPUB/article.xhtml").decode()


def test_build_epub_is_valid(tmp_path):
    data = build_epub("My Title", "<p>Body text here.</p>", url="http://x")
    assert data[:2] == b"PK"  # zip magic

    path = tmp_path / "book.epub"
    path.write_bytes(data)
    book = epub.read_epub(str(path))
    assert book.title == "My Title"


def test_build_epub_opens_on_the_article():
    data = build_epub("T", "<p>Body.</p>")
    opf = zipfile.ZipFile(io.BytesIO(data)).read("EPUB/content.opf").decode()
    spine = opf[opf.index("<spine") : opf.index("</spine>")]

    assert 'properties="nav"' in opf  # still required in the manifest
    assert spine.count("<itemref") == 1
    assert 'idref="nav"' not in spine


def test_build_epub_styles_and_byline():
    data = build_epub("A & B", "<p>Body.</p>", url="https://example.com/post?a=1&b=2")
    names = zipfile.ZipFile(io.BytesIO(data)).namelist()
    article = _article(data)

    assert "EPUB/style.css" in names
    assert 'href="style.css"' in article
    assert "<h1>A &amp; B</h1>" in article
    assert '<p class="source">' in article
    assert '<a href="https://example.com/post?a=1&amp;b=2">example.com</a>' in article


def test_build_epub_embeds_images_and_drops_missing():
    body = (
        '<p>One</p><img src="https://x/a.jpg?w=400"/>'
        '<p>Two</p><img src="https://x/b.png"/>'
        '<p>Three</p><img src="https://x/missing.jpg"/>'
    )
    images = {"https://x/a.jpg?w=400": JPEG, "https://x/b.png": PNG}
    data = build_epub("T", body, images=images)
    z = zipfile.ZipFile(io.BytesIO(data))
    article = _article(data)

    assert z.read("EPUB/images/img0.jpg") == JPEG[0]
    assert z.read("EPUB/images/img1.png") == PNG[0]
    assert '<img src="images/img0.jpg"/>' in article
    assert '<img src="images/img1.png"/>' in article
    assert "missing.jpg" not in article
    assert "https://x/" not in article


def test_build_epub_lead_image_is_cover_and_shown_first():
    images = {"https://x/lead.jpg": JPEG}
    data = build_epub("T", "<p>Body.</p>", images=images, lead_image="https://x/lead.jpg")
    z = zipfile.ZipFile(io.BytesIO(data))
    article = _article(data)

    assert z.read("EPUB/images/cover.jpg") == JPEG[0]
    assert 'properties="cover-image"' in z.read("EPUB/content.opf").decode()
    assert article.index('src="images/cover.jpg"') < article.index("<p>Body.</p>")


def test_build_epub_lead_image_not_repeated_when_in_body():
    body = '<p>Body.</p><img src="https://x/lead.jpg?w=400"/>'
    images = {"https://x/lead.jpg": JPEG, "https://x/lead.jpg?w=400": JPEG}
    data = build_epub("T", body, images=images, lead_image="https://x/lead.jpg")
    article = _article(data)

    assert article.count("<img") == 1
    assert article.index("<p>Body.</p>") < article.index("<img")
