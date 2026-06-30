"""Tests for local storage gateway."""

from pathlib import Path

import pytest

from app.core.config import Settings
from app.gateways.storage_gateway import LocalStorageGateway, get_storage_gateway


@pytest.mark.asyncio
async def test_local_storage_roundtrip(tmp_path: Path):
    gateway = LocalStorageGateway(tmp_path)

    presigned = await gateway.presign_upload(
        user_id="user-1", content_type="text/plain", size_bytes=5
    )
    assert presigned.api_upload is True

    await gateway.write_bytes(presigned.storage_key, b"hello")
    path = gateway.resolve_local_path(presigned.storage_key)
    assert path is not None
    assert path.read_bytes() == b"hello"

    url = await gateway.presign_download(presigned.storage_key)
    assert presigned.storage_key in url


def test_get_storage_gateway_defaults_to_local(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path))
    gateway = get_storage_gateway(Settings())
    assert isinstance(gateway, LocalStorageGateway)
