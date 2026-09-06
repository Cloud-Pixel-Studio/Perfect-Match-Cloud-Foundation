from __future__ import annotations

import argparse
import os
from uuid import uuid4

import boto3
from botocore import UNSIGNED
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import ClientError


def client(access_key: str | None = None, secret_key: str | None = None) -> BaseClient:
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("S3_ENDPOINT", "http://127.0.0.1:8333"),
        aws_access_key_id=access_key or os.environ["SEAWEEDFS_ACCESS_KEY"],
        aws_secret_access_key=secret_key or os.environ["SEAWEEDFS_SECRET_KEY"],
        region_name="us-east-1",
        config=Config(s3={"addressing_style": "path"}),
    )


PAYLOAD = b"Perfect Match Cloud disposable storage check."
PERSISTENCE_BUCKET = "pmc-foundation-persistence"
OBJECT_KEY = "checks/disposable.txt"


def full_smoke() -> None:
    bucket = f"pmc-foundation-{uuid4().hex[:12]}"
    s3 = client()

    s3.create_bucket(Bucket=bucket)
    s3.put_object(Bucket=bucket, Key=OBJECT_KEY, Body=PAYLOAD, Metadata={"scope": "pmc-00"})
    response = s3.get_object(Bucket=bucket, Key=OBJECT_KEY)
    assert response["Body"].read() == PAYLOAD
    s3.delete_object(Bucket=bucket, Key=OBJECT_KEY)
    s3.delete_bucket(Bucket=bucket)

    anonymous_denied = False
    try:
        unsigned = boto3.client(
            "s3",
            endpoint_url=os.environ.get("S3_ENDPOINT", "http://127.0.0.1:8333"),
            config=Config(signature_version=UNSIGNED, s3={"addressing_style": "path"}),
            region_name="us-east-1",
        )
        unsigned.list_buckets()
    except ClientError:
        anonymous_denied = True

    if not anonymous_denied:
        raise RuntimeError("Anonymous object-storage access was not denied")

    print("S3_WRITE=PASS")
    print("S3_READ=PASS")
    print("S3_DELETE=PASS")
    print("ANONYMOUS_ACCESS=DENIED")


def persistence_write() -> None:
    s3 = client()
    s3.create_bucket(Bucket=PERSISTENCE_BUCKET)
    s3.put_object(Bucket=PERSISTENCE_BUCKET, Key=OBJECT_KEY, Body=PAYLOAD)
    print("S3_PERSISTENCE_WRITE=PASS")


def persistence_read_delete() -> None:
    s3 = client()
    response = s3.get_object(Bucket=PERSISTENCE_BUCKET, Key=OBJECT_KEY)
    assert response["Body"].read() == PAYLOAD
    s3.delete_object(Bucket=PERSISTENCE_BUCKET, Key=OBJECT_KEY)
    s3.delete_bucket(Bucket=PERSISTENCE_BUCKET)
    print("S3_PERSISTENCE_READ=PASS")
    print("S3_PERSISTENCE_CLEANUP=PASS")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phase",
        choices=("full", "persistence-write", "persistence-read-delete"),
        default="full",
    )
    phase = parser.parse_args().phase
    if phase == "persistence-write":
        persistence_write()
    elif phase == "persistence-read-delete":
        persistence_read_delete()
    else:
        full_smoke()


if __name__ == "__main__":
    main()
