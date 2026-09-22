import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class Config:
    db_path: str
    s3_bucket: str
    s3_endpoint_url: str | None
    auth_token: str | None


def load_config() -> Config:
    load_dotenv()
    return Config(
        db_path=os.getenv("DATABASE_PATH", "reader.db"),
        s3_bucket=os.getenv("S3_BUCKET", ""),
        s3_endpoint_url=os.getenv("S3_ENDPOINT_URL") or None,
        auth_token=os.getenv("AUTH_TOKEN") or None,
    )
