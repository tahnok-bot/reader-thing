from html import escape

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from .config import Config, load_config
from .db import connect, get_article, list_articles
from .pipeline import process_url
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
    def create(request: Request, url: str = Form(...)):
        check_auth(request)
        try:
            process_url(url, conn, storage)
        except Exception as e:
            raise HTTPException(400, f"could not process: {e}")
        token = request.query_params.get("token", "")
        return RedirectResponse("/" + (f"?token={token}" if token else ""), status_code=303)

    @app.get("/articles")
    def api_list(request: Request):
        check_auth(request)
        return [dict(r) for r in list_articles(conn)]

    @app.get("/articles/{article_id}")
    def download(article_id: int, request: Request):
        check_auth(request)
        row = get_article(conn, article_id)
        if not row:
            raise HTTPException(404, "not found")
        return Response(
            content=storage.get(row["s3_key"]),
            media_type=EPUB_TYPE,
            headers={"Content-Disposition": f'attachment; filename="{article_id}.epub"'},
        )

    return app


def _page(rows, token: str = "") -> str:
    q = f"?token={escape(token)}" if token else ""
    items = "".join(
        f'<li><a href="/articles/{r["id"]}{q}">{escape(r["title"])}</a> '
        f'<small>{escape(r["url"])}</small></li>'
        for r in rows
    )
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
