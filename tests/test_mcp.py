import json

import pytest
from fastapi.testclient import TestClient

from reader_thing.app import create_app
from reader_thing.config import Config

HEADERS = {
    "Accept": "application/json, text/event-stream",
    "MCP-Protocol-Version": "2025-06-18",
}


@pytest.fixture
def mcp_client(conn, storage):
    config = Config(
        db_path=":memory:", s3_bucket="", s3_endpoint_url=None, auth_token="s3cret"
    )
    with TestClient(create_app(config=config, conn=conn, storage=storage)) as c:
        yield c


def rpc(client, method, params=None, token=None):
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    auth = {"Authorization": f"Bearer {token}"} if token else {}
    return client.post("/mcp", json=body, headers={**HEADERS, **auth})


def test_requires_token(mcp_client):
    assert rpc(mcp_client, "tools/list").status_code == 401
    assert rpc(mcp_client, "tools/list", token="nope").status_code == 401


def test_token_in_query_string(mcp_client):
    r = mcp_client.post(
        "/mcp?token=s3cret",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        headers=HEADERS,
    )
    assert [t["name"] for t in r.json()["result"]["tools"]] == ["save_for_later"]


def test_save_for_later(mcp_client, storage):
    r = rpc(
        mcp_client,
        "tools/call",
        {"name": "save_for_later", "arguments": {"markdown": "# Findings\n\nText."}},
        token="s3cret",
    )
    result = r.json()["result"]
    assert not result["isError"]
    assert json.loads(result["content"][0]["text"]) == {"id": 1, "title": "Findings"}

    items = mcp_client.get("/articles?token=s3cret").json()
    assert items[0]["title"] == "Findings" and "markdown" not in items[0]
    assert mcp_client.get("/articles/1?token=s3cret").content[:2] == b"PK"
