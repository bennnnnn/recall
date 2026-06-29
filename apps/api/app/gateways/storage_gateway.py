"""Storage gateway abstraction — swap R2/S3/local via config."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.core.config import Settings


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

    def resolve_local_path(self, storage_key: str) -> Path | None: ...


class LocalStorageGateway:
    """Dev/test storage — files under STORAGE_LOCAL_PATH."""

    def __init__(self, base_path: Path) -> None:
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)

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
        return f"file://{self.base_path / storage_key}"

    async def write_bytes(self, storage_key: str, data: bytes) -> None:
        path = self.local_path(storage_key)
        path.write_bytes(data)

    def resolve_local_path(self, storage_key: str) -> Path | None:
        path = self.base_path / storage_key
        return path if path.is_file() else None

    def local_path(self, storage_key: str) -> Path:
        path = self.base_path / storage_key
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


def get_storage_gateway(settings: Settings) -> LocalStorageGateway:
    backend = os.environ.get("STORAGE_BACKEND", "local").lower()
    if backend == "local":
        root = Path(os.environ.get("STORAGE_LOCAL_PATH", "/tmp/recall-attachments"))
        return LocalStorageGateway(root)
    root = Path("/tmp/recall-attachments")
    return LocalStorageGateway(root)
