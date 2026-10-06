# reader-thing

A personal read-it-later service. Send it a URL, get back an EPUB to read on
[KOReader](https://koreader.rocks/).

## How it works

Submit a web page URL through a simple page. It fetches the HTML, extracts the
article, converts it to a clean EPUB, and stores it, ready to read on your
device. PDF and EPUB URLs are stored as-is, titled from their metadata.

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

- **Process** — `uv run reader-thing serve`, listening on `$HOST:$PORT`
  (default `0.0.0.0:8000`). No reverse proxy or TLS in front of it; clients hit
  `http://zoltan:8000` directly.
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

The server doesn't reload code on its own, so after pulling:

```sh
git pull && uv sync
systemctl --user restart reader-thing
```

## Roadmap

- Accept uploaded files, not just URLs.
- Scheduled agent runs that fetch articles from a site matching a filter prompt.
