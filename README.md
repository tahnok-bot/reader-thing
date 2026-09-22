# reader-thing

A personal read-it-later service. Send it a URL, get back an EPUB to read on
[KOReader](https://koreader.rocks/).

## How it works

Give it a web page URL. It extracts the article, converts it to a clean EPUB,
and stores it, ready to read on your device.

## Architecture

- **Storage** — EPUBs live in an S3 bucket.
- **State** — everything else in a local SQLite database.
- **Auth** — single user, so a shared secret is enough.

## Roadmap

- Accept PDFs and plain EPUBs, not just web pages.
- Scheduled agent runs that fetch articles from a site matching a filter prompt.
