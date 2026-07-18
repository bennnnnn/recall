"""Storage gateway abstraction — swap R2/S3/local via config.

``local`` writes to disk (dev). ``r2`` presigns Cloudflare R2 (S3-compatible)
upload/download URLs so the mobile client talks to object storage directly —
blobs never stream through the API, and storage credentials stay server-side.
The client gets a short-lived signed PUT URL at presign time and a signed GET
URL on download. ``api_upload`` tells the client whether to PUT to the API
(local) or directly to the presigned URL (R2).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.core.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PresignedUpload:
    attachment_id: str
    upload_url: str
    storage_key: str
    headers: dict[str, str]
    api_upload: bool = False


class StorageGateway(Protocol):
    async def presign_upload(
        self, *, user_id: str, content_type: str, size_bytes: int
    ) -> PresignedUpload: ...

    async def presign_download(self, storage_key: str) -> str: ...

    async def write_bytes(self, storage_key: str, data: bytes) -> None: ...

    async def read_bytes(self, storage_key: str) -> bytes | None: ...

    async def delete_bytes(self, storage_key: str) -> None: ...

    def resolve_local_path(self, storage_key: str) -> Path | None: ...


class LocalStorageGateway:
    """Dev/test storage — files under STORAGE_LOCAL_PATH."""

    def __init__(self, base_path: Path) -> None:
        self.base_path = base_path.resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _path_under_base(self, storage_key: str) -> Path:
        """Resolve ``storage_key`` and reject path escape (``..`` / absolute)."""
        if not storage_key or storage_key.startswith("/") or ".." in Path(storage_key).parts:
            raise ValueError("Invalid storage key")
        path = (self.base_path / storage_key).resolve()
        if not path.is_relative_to(self.base_path):
            raise ValueError("Invalid storage key")
        return path

    async def presign_upload(
        self, *, user_id: str, content_type: str, size_bytes: int
    ) -> PresignedUpload:
        attachment_id = str(uuid.uuid4())
        storage_key = f"{user_id}/{attachment_id}"
        return PresignedUpload(
            attachment_id=attachment_id,
            upload_url=f"/attachments/{attachment_id}/upload",
            storage_key=storage_key,
            headers={"Content-Type": content_type, "Content-Length": str(size_bytes)},
            api_upload=True,
        )

    async def presign_download(self, storage_key: str) -> str:
        return f"file://{self._path_under_base(storage_key)}"

    async def write_bytes(self, storage_key: str, data: bytes) -> None:
        path = self.local_path(storage_key)
        path.write_bytes(data)

    async def read_bytes(self, storage_key: str) -> bytes | None:
        path = self.resolve_local_path(storage_key)
        return path.read_bytes() if path is not None else None

    async def delete_bytes(self, storage_key: str) -> None:
        try:
            path = self._path_under_base(storage_key)
        except ValueError:
            return
        try:
            path.unlink(missing_ok=True)
        except IsADirectoryError:
            pass

    def resolve_local_path(self, storage_key: str) -> Path | None:
        try:
            path = self._path_under_base(storage_key)
        except ValueError:
            return None
        return path if path.is_file() else None

    def local_path(self, storage_key: str) -> Path:
        path = self._path_under_base(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


class R2StorageGateway:
    """Cloudflare R2 (S3-compatible) — presigned PUT/GET URLs, no blob I/O here.

    boto3's ``generate_presigned_url`` is an offline Signature V4 computation
    (no network call), so it's safe to run directly in the async path; we still
    offload to a thread to honour the async contract and keep boto3's brief
    import/construct cost off the event loop.
    """

    def __init__(self, settings: Settings) -> None:
        import boto3  # local import — keeps dev (no boto3 hot path) light

        endpoint = settings.r2_endpoint or (
            f"https://{settings.r2_account_id}.r2.cloudflarestorage.com"
        )
        self._bucket = settings.r2_bucket
        self._expiry = settings.r2_presign_expiry_seconds
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            region_name="auto",  # R2 ignores region but boto3 requires one
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
        )

    async def presign_upload(
        self, *, user_id: str, content_type: str, size_bytes: int
    ) -> PresignedUpload:
        import asyncio

        attachment_id = str(uuid.uuid4())
        storage_key = f"{user_id}/{attachment_id}"
        # R2/S3 presigned PUT — the client uploads directly; the signed URL
        # pins Content-Type so a swapped MIME can't be stored under this URL.
        url = await asyncio.to_thread(
            self._client.generate_presigned_url,
            "put_object",
            Params={
                "Bucket": self._bucket,
                "Key": storage_key,
                "ContentType": content_type,
                "ContentLength": size_bytes,
            },
            ExpiresIn=self._expiry,
        )
        return PresignedUpload(
            attachment_id=attachment_id,
            upload_url=url,
            storage_key=storage_key,
            # The client must send these exact headers for the signature to match.
            headers={"Content-Type": content_type, "Content-Length": str(size_bytes)},
            api_upload=False,
        )

    async def presign_download(self, storage_key: str) -> str:
        import asyncio

        return await asyncio.to_thread(
            self._client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self._bucket, "Key": storage_key},
            ExpiresIn=self._expiry,
        )

    async def write_bytes(self, storage_key: str, data: bytes) -> None:
        import asyncio

        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=storage_key,
            Body=data,
        )

    async def read_bytes(self, storage_key: str) -> bytes | None:
        # Used by attachment_content to extract text/vision bytes for the prompt.
        # get_object is a real network call — offload to a thread.
        import asyncio

        try:
            resp = await asyncio.to_thread(
                self._client.get_object, Bucket=self._bucket, Key=storage_key
            )
            body = await asyncio.to_thread(lambda: resp["Body"].read())
            return body
        except Exception:
            logger.debug("R2 get_object failed for %s", storage_key, exc_info=True)
            return None

    async def delete_bytes(self, storage_key: str) -> None:
        import asyncio

        try:
            await asyncio.to_thread(
                self._client.delete_object, Bucket=self._bucket, Key=storage_key
            )
        except Exception:
            logger.debug("R2 delete_object failed for %s", storage_key, exc_info=True)

    def resolve_local_path(self, storage_key: str) -> Path | None:
        return None


class UnconfiguredStorageGateway:
    """Fail closed when production expects R2 but credentials are missing."""

    _msg = "Object storage is not configured"

    async def presign_upload(
        self, *, user_id: str, content_type: str, size_bytes: int
    ) -> PresignedUpload:
        raise RuntimeError(self._msg)

    async def presign_download(self, storage_key: str) -> str:
        raise RuntimeError(self._msg)

    async def write_bytes(self, storage_key: str, data: bytes) -> None:
        raise RuntimeError(self._msg)

    async def read_bytes(self, storage_key: str) -> bytes | None:
        return None

    async def delete_bytes(self, storage_key: str) -> None:
        return None

    def resolve_local_path(self, storage_key: str) -> Path | None:
        return None


def _r2_configured(settings: Settings) -> bool:
    return bool(
        settings.r2_account_id
        and settings.r2_access_key_id
        and settings.r2_secret_access_key
        and settings.r2_bucket
    )


def get_storage_gateway(settings: Settings) -> StorageGateway:
    backend = settings.storage_backend.strip().lower()
    if backend == "r2":
        if _r2_configured(settings):
            return R2StorageGateway(settings)
        # Credentials not set yet. In dev, fall back to local so the app keeps
        # working; in production the attachment routes return 501 for non-local
        # backends, which is safer than silently storing to /tmp in prod.
        if settings.environment == "development":
            logger.warning(
                "STORAGE_BACKEND=r2 but R2 credentials are incomplete — "
                "falling back to local storage. Set r2_* secrets before production."
            )
            return LocalStorageGateway(Path(settings.storage_local_path))
        logger.error("R2 storage selected but credentials incomplete in production")
        return UnconfiguredStorageGateway()
    # default: local
    return LocalStorageGateway(Path(settings.storage_local_path))
