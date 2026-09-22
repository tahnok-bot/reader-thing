from typing import Protocol

EPUB_TYPE = "application/epub+zip"


class Storage(Protocol):
    def put(self, key: str, data: bytes, content_type: str = EPUB_TYPE) -> None: ...
    def get(self, key: str) -> bytes: ...


class MemoryStorage:
    """In-memory storage, used by tests."""

    def __init__(self) -> None:
        self._items: dict[str, bytes] = {}

    def put(self, key, data, content_type=EPUB_TYPE) -> None:
        self._items[key] = data

    def get(self, key) -> bytes:
        return self._items[key]


class S3Storage:
    def __init__(self, bucket: str, endpoint_url: str | None = None, client=None):
        import boto3

        self.bucket = bucket
        self.client = client or boto3.client("s3", endpoint_url=endpoint_url)

    def put(self, key, data, content_type=EPUB_TYPE) -> None:
        self.client.put_object(
            Bucket=self.bucket, Key=key, Body=data, ContentType=content_type
        )

    def get(self, key) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
