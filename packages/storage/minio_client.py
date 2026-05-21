import io
import uuid
from pathlib import Path

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from packages.config import get_settings

_LOCAL_STORAGE = Path("/tmp/underwrite-agent/storage")


class StorageClient:
    def __init__(self):
        s = get_settings()
        self.bucket = s.minio_bucket
        self._use_local = False
        protocol = "https" if s.minio_secure else "http"
        endpoint = f"{protocol}://{s.minio_endpoint}"
        try:
            self.client = boto3.client(
                "s3",
                endpoint_url=endpoint,
                aws_access_key_id=s.minio_access_key,
                aws_secret_access_key=s.minio_secret_key,
                config=Config(signature_version="s3v4"),
                region_name="us-east-1",
            )
            self._ensure_bucket()
        except Exception:
            self._use_local = True
            _LOCAL_STORAGE.mkdir(parents=True, exist_ok=True)

    def _ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError:
            try:
                self.client.create_bucket(Bucket=self.bucket)
            except Exception:
                self._use_local = True
                _LOCAL_STORAGE.mkdir(parents=True, exist_ok=True)

    def upload(self, tenant_id: str, filename: str, data: bytes, prefix: str = "cases") -> str:
        key = f"{prefix}/{tenant_id}/{uuid.uuid4()}/{filename}"
        if self._use_local:
            path = _LOCAL_STORAGE / key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            return key
        self.client.upload_fileobj(io.BytesIO(data), self.bucket, key)
        return key

    def download(self, key: str) -> bytes:
        if self._use_local:
            return (_LOCAL_STORAGE / key).read_bytes()
        buf = io.BytesIO()
        self.client.download_fileobj(self.bucket, key, buf)
        return buf.getvalue()
