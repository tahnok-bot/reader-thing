import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime
from html import escape

from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, Request
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Response,
)

from .config import Config, load_config
from .db import connect, get_article, insert_pending, list_articles
from .pipeline import process_pending
from .storage import EPUB_TYPE, S3Storage


def create_app(config: Config | None = None, conn=None, storage=None) -> FastAPI:
    config = config or load_config()
    conn = conn or connect(config.db_path)
    storage = storage or S3Storage(
        config.s3_bucket, endpoint_url=config.s3_endpoint_url
    )

    app = FastAPI(title="reader-thing")
    app.state.conn = conn
    app.state.storage = storage
    app.state.config = config

    def check_auth(request: Request) -> None:
        if not config.auth_token:
            return
        auth = request.headers.get("authorization", "")
        got = auth[7:] if auth.startswith("Bearer ") else request.query_params.get("token")
        if got != config.auth_token:
            raise HTTPException(401, "bad token")

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        return _page(list_articles(conn), request.query_params.get("token", ""))

    @app.post("/articles")
    def create(request: Request, background: BackgroundTasks, url: str = Form(...)):
        check_auth(request)
        article_id = insert_pending(conn, url)
        background.add_task(process_pending, conn, storage, article_id, url)
        # The browser submit page wants to land back on the list; API clients
        # (e.g. the Android share shortcut) want a body they can read.
        if "text/html" in request.headers.get("accept", ""):
            token = request.query_params.get("token", "")
            dest = "/" + (f"?token={token}" if token else "")
            return RedirectResponse(dest, status_code=303)
        return JSONResponse(
            {"id": article_id, "url": url, "status": "pending"}, status_code=202
        )

    @app.get("/articles")
    def api_list(request: Request):
        check_auth(request)
        return [dict(r) for r in list_articles(conn)]

    @app.get("/feed.xml")
    def feed(request: Request):
        # For KOReader's News Downloader: with "download full article" on,
        # it fetches each item link and saves the EPUB as-is.
        check_auth(request)
        ready = [r for r in list_articles(conn) if r["status"] == "ready"]
        return Response(
            content=_rss(ready, str(request.base_url).rstrip("/")),
            media_type="application/rss+xml",
        )

    @app.get("/articles/{article_id}")
    def download(article_id: int, request: Request):
        check_auth(request)
        row = get_article(conn, article_id)
        if not row:
            raise HTTPException(404, "not found")
        if row["status"] != "ready":
            raise HTTPException(409, f"not ready: {row['status']}")
        return Response(
            content=storage.get(row["s3_key"]),
            media_type=EPUB_TYPE,
            headers={"Content-Disposition": f'attachment; filename="{article_id}.epub"'},
        )

    return app


def _rss(rows, base: str) -> bytes:
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "reader-thing"
    ET.SubElement(channel, "link").text = f"{base}/"
    ET.SubElement(channel, "description").text = "Saved articles as EPUB"
    for r in rows:
        link = f"{base}/articles/{r['id']}"
        created = datetime.fromisoformat(r["created_at"]).replace(tzinfo=timezone.utc)
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = r["title"]
        ET.SubElement(item, "link").text = link
        ET.SubElement(item, "guid").text = link
        ET.SubElement(item, "pubDate").text = format_datetime(created)
        ET.SubElement(item, "description").text = r["url"]
        ET.SubElement(item, "enclosure", url=link, type=EPUB_TYPE, length="0")
    return ET.tostring(rss, encoding="utf-8", xml_declaration=True)


def _page(rows, token: str = "") -> str:
    q = f"?token={escape(token)}" if token else ""

    def render(r) -> str:
        title, url, status = escape(r["title"]), escape(r["url"]), r["status"]
        if status == "ready":
            head = f'<a href="/articles/{r["id"]}{q}">{title}</a>'
        else:
            head = f'{title} <em>[{escape(status)}]</em>'
        return f'<li>{head} <small>{url}</small></li>'

    items = "".join(render(r) for r in rows)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>reader-thing</title></head>
<body>
<h1>reader-thing</h1>
<form method="post" action="/articles{q}">
  <input name="url" type="url" placeholder="https://..." required size="40">
  <button type="submit">Add</button>
</form>
<ul>{items}</ul>
</body></html>"""
