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
from starlette.routing import Route

from .config import Config, load_config
from .db import (
    connect,
    delete_article,
    get_article,
    insert_pending,
    list_articles,
    mark_pending,
    set_archived,
)
from .mcp_server import create_mcp
from .pipeline import process_pending
from .storage import S3Storage, media_type


def create_app(config: Config | None = None, conn=None, storage=None) -> FastAPI:
    config = config or load_config()
    conn = conn or connect(config.db_path)
    storage = storage or S3Storage(
        config.s3_bucket, endpoint_url=config.s3_endpoint_url
    )

    mcp, mcp_app = create_mcp(conn, storage)
    app = FastAPI(title="reader-thing", lifespan=lambda _: mcp.session_manager.run())
    app.state.conn = conn
    app.state.storage = storage
    app.state.config = config
    app.router.routes.append(
        Route("/mcp", endpoint=_RequireToken(mcp_app, config.auth_token))
    )

    def check_auth(request: Request) -> None:
        if not _authorized(request, config.auth_token):
            raise HTTPException(401, "bad token")

    def done(request: Request, body: dict, status_code: int = 200):
        # The browser page wants to land back on the list; API clients
        # (e.g. the Android share shortcut) want a body they can read.
        if "text/html" in request.headers.get("accept", ""):
            token = request.query_params.get("token", "")
            dest = "/" + (f"?token={token}" if token else "")
            return RedirectResponse(dest, status_code=303)
        return JSONResponse(body, status_code=status_code)

    def existing(article_id: int):
        row = get_article(conn, article_id)
        if not row:
            raise HTTPException(404, "not found")
        return row

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        return _page(list_articles(conn), request.query_params.get("token", ""))

    @app.post("/articles")
    def create(request: Request, background: BackgroundTasks, url: str = Form(...)):
        check_auth(request)
        article_id = insert_pending(conn, url)
        background.add_task(process_pending, conn, storage, article_id, url)
        return done(request, {"id": article_id, "url": url, "status": "pending"}, 202)

    @app.post("/articles/{article_id}/retry")
    def retry(article_id: int, request: Request, background: BackgroundTasks):
        # Also covers rows stuck pending because the server restarted mid-fetch.
        check_auth(request)
        row = existing(article_id)
        if row["status"] == "ready":
            raise HTTPException(409, "already ready")
        mark_pending(conn, article_id)
        background.add_task(process_pending, conn, storage, article_id, row["url"])
        return done(request, {"id": article_id, "status": "pending"}, 202)

    @app.post("/articles/{article_id}/archive")
    def archive(article_id: int, request: Request):
        check_auth(request)
        existing(article_id)
        set_archived(conn, article_id, True)
        return done(request, {"id": article_id, "archived": True})

    @app.post("/articles/{article_id}/unarchive")
    def unarchive(article_id: int, request: Request):
        check_auth(request)
        existing(article_id)
        set_archived(conn, article_id, False)
        return done(request, {"id": article_id, "archived": False})

    @app.post("/articles/{article_id}/delete")
    def delete(article_id: int, request: Request):
        check_auth(request)
        row = existing(article_id)
        # Object first: if that fails the row survives and you can try again,
        # rather than leaving an orphan in the bucket nothing points at.
        if row["s3_key"]:
            storage.delete(row["s3_key"])
        delete_article(conn, article_id)
        return done(request, {"id": article_id, "deleted": True})

    @app.get("/articles")
    def api_list(request: Request):
        check_auth(request)
        return [
            {k: r[k] for k in r.keys() if k != "markdown"} for r in list_articles(conn)
        ]

    @app.get("/feed.xml")
    def feed(request: Request):
        # For KOReader's News Downloader: with "download full article" on,
        # it fetches each item link and saves the EPUB (or PDF) as-is.
        check_auth(request)
        ready = [
            r for r in list_articles(conn)
            if r["status"] == "ready" and not r["archived"]
        ]
        return Response(
            content=_rss(ready, str(request.base_url).rstrip("/")),
            media_type="application/rss+xml",
        )

    @app.get("/articles/{article_id}")
    def download(article_id: int, request: Request):
        check_auth(request)
        row = existing(article_id)
        if row["status"] != "ready":
            raise HTTPException(409, f"not ready: {row['status']}")
        key = row["s3_key"]
        ext = key.rsplit(".", 1)[-1]
        return Response(
            content=storage.get(key),
            media_type=media_type(key),
            headers={"Content-Disposition": f'attachment; filename="{article_id}.{ext}"'},
        )

    return app


def _authorized(request: Request, token: str | None) -> bool:
    if not token:
        return True
    auth = request.headers.get("authorization", "")
    got = auth[7:] if auth.startswith("Bearer ") else request.query_params.get("token")
    return got == token


class _RequireToken:
    """Same shared-secret check as the API, around a plain ASGI app."""

    def __init__(self, app, token):
        self.app, self.token = app, token

    async def __call__(self, scope, receive, send):
        if not _authorized(Request(scope), self.token):
            response = JSONResponse({"detail": "bad token"}, status_code=401)
            return await response(scope, receive, send)
        await self.app(scope, receive, send)


def _rss(rows, base: str) -> bytes:
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "reader-thing"
    ET.SubElement(channel, "link").text = f"{base}/"
    ET.SubElement(channel, "description").text = "Saved articles as EPUB or PDF"
    for r in rows:
        link = f"{base}/articles/{r['id']}"
        created = datetime.fromisoformat(r["created_at"]).replace(tzinfo=timezone.utc)
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = r["title"]
        ET.SubElement(item, "link").text = link
        ET.SubElement(item, "guid").text = link
        ET.SubElement(item, "pubDate").text = format_datetime(created)
        ET.SubElement(item, "description").text = r["url"]
        ET.SubElement(
            item, "enclosure", url=link, type=media_type(r["s3_key"]), length="0"
        )
    return ET.tostring(rss, encoding="utf-8", xml_declaration=True)


def _page(rows, token: str = "") -> str:
    q = f"?token={escape(token)}" if token else ""

    def button(article_id, action, label, confirm=None) -> str:
        onsubmit = f' onsubmit="return confirm(\'{confirm}\')"' if confirm else ""
        return (
            f'<form method="post" action="/articles/{article_id}/{action}{q}"{onsubmit}>'
            f'<button type="submit">{label}</button></form>'
        )

    def render(r) -> str:
        aid, title, url, status = r["id"], escape(r["title"]), escape(r["url"]), r["status"]
        if status == "ready":
            head = f'<a href="/articles/{aid}{q}">{title}</a>'
        else:
            head = f'{title} <em>[{escape(status)}]</em>'
            if r["error"]:
                head += f' <small class="error">{escape(r["error"])}</small>'
        buttons = []
        if status != "ready":
            buttons.append(button(aid, "retry", "Retry"))
        if r["archived"]:
            buttons.append(button(aid, "unarchive", "Unarchive"))
        else:
            buttons.append(button(aid, "archive", "Archive"))
        buttons.append(button(aid, "delete", "Delete", confirm="Delete this article?"))
        return (
            f'<li>{head} <small>{url}</small>'
            f'<span class="actions">{"".join(buttons)}</span></li>'
        )

    active = "".join(render(r) for r in rows if not r["archived"])
    archived = [r for r in rows if r["archived"]]
    archived_section = (
        f'<details><summary>Archived ({len(archived)})</summary>'
        f'<ul>{"".join(render(r) for r in archived)}</ul></details>'
        if archived else ""
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>reader-thing</title>
<style>
  li {{ margin-bottom: 0.5em; }}
  .actions form {{ display: inline; margin-left: 0.3em; }}
  .error {{ color: #b00; }}
</style></head>
<body>
<h1>reader-thing</h1>
<form method="post" action="/articles{q}">
  <input name="url" type="url" placeholder="https://..." required size="40">
  <button type="submit">Add</button>
</form>
<ul>{active}</ul>
{archived_section}
</body></html>"""
