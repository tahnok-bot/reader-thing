# reader-thing

A personal read-it-later service. Send it a URL, get back an EPUB to read on
[KOReader](https://koreader.rocks/).

## How it works

Submit a web page URL through a simple page. It fetches the HTML, extracts the
article, converts it to a clean EPUB, and stores it, ready to read on your
device. PDF and EPUB URLs are stored as-is, titled from their metadata.

Agents can also push Markdown over [MCP](#mcp); it's converted to an EPUB the
same way.

From the list you can retry a failed (or stuck pending) article, archive one
(it drops out of the feed and into a collapsed section), or delete it along with
its stored file.

## Architecture

- **Language** — Python. FastAPI serving a JSON API and a basic submit page.
- **Extraction** — `trafilatura` on the fetched HTML.
- **EPUB** — `ebooklib`. **PDF** — `pypdf`, just for the title.
- **Storage** — EPUBs live in an S3 bucket; their object keys are recorded in
  SQLite.
- **State** — everything else in a local SQLite database.
- **Config** — S3 credentials, bucket name, and the auth token are read from
  the environment / a `.env` file.
- **Auth** — single user, so a shared secret is enough.

## MCP

`/mcp` is a [Model Context Protocol](https://modelcontextprotocol.io/) endpoint
(streamable HTTP, stateless) with one tool, `save_for_later(markdown, title?,
source_url?)`. It uses the same token as everything else, as a header or, for
clients that only take a URL, `?token=`:

```sh
claude mcp add --transport http reader https://reader.zoltanlabs.ca/mcp \
  --header "Authorization: Bearer $AUTH_TOKEN"
```

The Markdown is kept in the database, so `reprocess` rebuilds those articles
from it rather than fetching anything.

## Development

Managed with [uv](https://docs.astral.sh/uv/).

```sh
uv sync --extra dev   # install deps
uv run pytest         # run tests
uv run reader-thing   # serve on $HOST:$PORT (default :8000)

uv run reader-thing build URL [-o out.epub]   # EPUB to a local file; no DB/S3
uv run reader-thing reprocess ID... | --all  # rebuild stored articles in place
```

`build` is handy for previewing extraction changes. `reprocess` picks those
changes up for articles you've already saved, overwriting their EPUBs in S3.

Copy `.env.example` to `.env` and fill in the S3 bucket, credentials, and auth
token first.

## Deployment

Runs on `zoltan`, from the checkout at `/data/src/reader-thing`, as user
`tahnok`.

- **Process** — `uv run reader-thing serve`, listening on `127.0.0.1:8000`
  (`HOST` is set by a local drop-in,
  `~/.config/systemd/user/reader-thing.service.d/bind-localhost.conf`).
- **Proxy** — Caddy (`/etc/caddy/Caddyfile`) terminates TLS and serves it at
  `https://reader.zoltanlabs.ca/`.
- **Config** — `.env` in the checkout (not in git); see `.env.example`.
- **Database** — `reader.db` (SQLite) in the checkout. Back this up; it's the
  only record of which S3 objects belong to which article.
- **Objects** — Garage S3 at `https://objects.tahnok.ca`, bucket
  `reader-thing`, path-style addressing.
- **Auth** — set `AUTH_TOKEN` to require `Authorization: Bearer <token>` or
  `?token=<token>`. Empty means no auth.

### Running it as a service

`deploy/reader-thing.service` is a systemd user unit for the setup above. It
restarts on failure and, since lingering is enabled for `tahnok`, starts at
boot.

```sh
ln -s /data/src/reader-thing/deploy/reader-thing.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now reader-thing
journalctl --user -u reader-thing -f   # logs
```

### Updating

The service runs straight out of this checkout, so there's nothing to pull when
you're working on `zoltan`. Edits here are what it runs, and `uv sync` / `uv add`
change its virtualenv right away. The server doesn't reload code on its own, so
restart it to pick up changes:

```sh
uv sync   # only if dependencies changed
systemctl --user restart reader-thing
```

If changes were pushed from elsewhere, `git pull` first. Schema changes migrate
the live `reader.db` on startup.

## Roadmap

- Accept uploaded files, not just URLs.
- Scheduled agent runs that fetch articles from a site matching a filter prompt.
