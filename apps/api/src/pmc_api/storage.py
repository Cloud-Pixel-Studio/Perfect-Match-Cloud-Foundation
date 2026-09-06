from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, BinaryIO, Protocol

import boto3
from botocore.config import Config

if TYPE_CHECKING:
    from mypy_boto3_s3.client import S3Client

from pmc_api.config import Settings, get_settings


class ObjectStorage(Protocol):
    def create_bucket(self, bucket: str) -> None: ...

    def put_object(self, bucket: str, key: str, body: bytes | BinaryIO) -> None: ...

    def get_object(self, bucket: str, key: str) -> bytes: ...

    def delete_object(self, bucket: str, key: str) -> None: ...

    def object_metadata(self, bucket: str, key: str) -> dict[str, object]: ...

    def healthcheck(self) -> bool: ...


class S3ObjectStorage:
    def __init__(self, settings: Settings) -> None:
        self._client: S3Client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            config=Config(s3={"addressing_style": "path"}),
        )

    def create_bucket(self, bucket: str) -> None:
        self._client.create_bucket(Bucket=bucket)

    def put_object(self, bucket: str, key: str, body: bytes | BinaryIO) -> None:
        self._client.put_object(Bucket=bucket, Key=key, Body=body)

    def get_object(self, bucket: str, key: str) -> bytes:
        response = self._client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read()

    def delete_object(self, bucket: str, key: str) -> None:
        self._client.delete_object(Bucket=bucket, Key=key)

    def object_metadata(self, bucket: str, key: str) -> dict[str, object]:
        response = self._client.head_object(Bucket=bucket, Key=key)
        return {"content_length": response["ContentLength"], "metadata": response["Metadata"]}

    def healthcheck(self) -> bool:
        try:
            self._client.list_buckets()
        except Exception:
            return False
        return True


@lru_cache
def get_object_storage() -> S3ObjectStorage:
    return S3ObjectStorage(get_settings())


def object_storage_is_ready() -> bool:
    return get_object_storage().healthcheck()
