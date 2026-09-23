# reader-thing

A personal read-it-later service. Send it a URL, get back an EPUB to read on
[KOReader](https://koreader.rocks/).

## How it works

Submit a web page URL through a simple page. It fetches the HTML, extracts the
article, converts it to a clean EPUB, and stores it, ready to read on your
device.

## Architecture

- **Language** — Python. FastAPI serving a JSON API and a basic submit page.
- **Extraction** — `trafilatura` on the fetched HTML.
- **EPUB** — `ebooklib`.
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
uv run reader-thing   # serve on :8000

uv run reader-thing build URL [-o out.epub]   # EPUB to a local file; no DB/S3
uv run reader-thing reprocess ID... | --all  # rebuild stored articles in place
```

`build` is handy for previewing extraction changes. `reprocess` picks those
changes up for articles you've already saved, overwriting their EPUBs in S3.

Copy `.env.example` to `.env` and fill in the S3 bucket, credentials, and auth
token first.

## Roadmap

- Accept PDFs and plain EPUBs, not just web pages.
- Scheduled agent runs that fetch articles from a site matching a filter prompt.
