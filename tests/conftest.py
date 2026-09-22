import pytest
from fastapi.testclient import TestClient

from reader_thing.app import create_app
from reader_thing.config import Config
from reader_thing.db import connect
from reader_thing.storage import MemoryStorage

SAMPLE_HTML = """<!doctype html><html><head><title>Test Article</title></head>
<body><article><h1>Test Article</h1>
<p>Hello world, this is the body of the article with enough text to be
extracted by trafilatura reliably as the main content of the page.</p>
<p>A second paragraph with more meaningful content so the extractor is
confident this block is the article and keeps it in the output.</p>
</article></body></html>"""


@pytest.fixture
def sample_html():
    return SAMPLE_HTML


@pytest.fixture
def conn():
    c = connect(":memory:")
    yield c
    c.close()


@pytest.fixture
def storage():
    return MemoryStorage()


@pytest.fixture
def client(conn, storage, monkeypatch):
    monkeypatch.setattr("reader_thing.extract.fetch", lambda url: SAMPLE_HTML)
    config = Config(
        db_path=":memory:", s3_bucket="", s3_endpoint_url=None, auth_token=None
    )
    app = create_app(config=config, conn=conn, storage=storage)
    return TestClient(app)
