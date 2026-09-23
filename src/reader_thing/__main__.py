import argparse
import re
import sys
from pathlib import Path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="reader-thing")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("serve", help="run the web service on :8000 (the default)")

    p = sub.add_parser("build", help="build an EPUB for a URL into a local file")
    p.add_argument("url")
    p.add_argument("-o", "--output", type=Path, help="default: <title>.epub")

    p = sub.add_parser("reprocess", help="rebuild stored articles in place")
    p.add_argument("ids", nargs="*", type=int, metavar="ID")
    p.add_argument("--all", action="store_true", help="every stored article")

    args = parser.parse_args(argv)
    if args.command == "build":
        return _build(args.url, args.output)
    if args.command == "reprocess":
        if not args.ids and not args.all:
            parser.error("reprocess needs article IDs or --all")
        return _reprocess(args.ids, args.all)
    _serve()
    return 0


def _serve() -> None:
    import uvicorn

    from .app import create_app

    uvicorn.run(create_app(), host="0.0.0.0", port=8000)


def _build(url, output) -> int:
    """Doesn't touch the database or S3, so it's safe for previewing changes."""
    from .pipeline import build

    title, data = build(url)
    output = output or Path(_filename(title) + ".epub")
    output.write_bytes(data)
    print(f"{title} -> {output}")
    return 0


def _reprocess(ids, everything, conn=None, storage=None) -> int:
    from .config import load_config
    from .db import connect, list_articles
    from .pipeline import reprocess
    from .storage import S3Storage

    config = load_config()
    conn = conn or connect(config.db_path)
    storage = storage or S3Storage(config.s3_bucket, endpoint_url=config.s3_endpoint_url)

    if everything:
        ids = [row["id"] for row in reversed(list_articles(conn))]
    failed = 0
    for article_id in ids:
        try:
            row = reprocess(conn, storage, article_id)
            print(f"{article_id}: {row['title']}")
        except Exception as e:  # noqa: BLE001 - report it and carry on with the rest
            failed += 1
            print(f"{article_id}: failed: {e}", file=sys.stderr)
    return 1 if failed else 0


def _filename(title: str) -> str:
    return re.sub(r"[^\w.-]+", "-", title).strip("-")[:80] or "article"


if __name__ == "__main__":
    sys.exit(main())
