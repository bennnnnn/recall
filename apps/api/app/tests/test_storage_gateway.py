"""Tests for local + R2 storage gateways."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings
from app.gateways.storage_gateway import (
    LocalStorageGateway,
    R2StorageGateway,
    UnconfiguredStorageGateway,
    get_storage_gateway,
)


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

    data = await gateway.read_bytes(presigned.storage_key)
    assert data == b"hello"


def test_get_storage_gateway_defaults_to_local(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path))
    gateway = get_storage_gateway(Settings())
    assert isinstance(gateway, LocalStorageGateway)


def _r2_settings() -> Settings:
    return Settings(
        storage_backend="r2",
        r2_account_id="acct",
        r2_access_key_id="key",
        r2_secret_access_key="secret",
        r2_bucket="recall-attachments",
        environment="development",
    )


def test_get_storage_gateway_uses_r2_when_configured():
    with patch("boto3.client") as mock_client:
        get_storage_gateway(_r2_settings())
        mock_client.assert_called_once()
        _, kwargs = mock_client.call_args
        assert kwargs["endpoint_url"] == "https://acct.r2.cloudflarestorage.com"
        assert kwargs["aws_access_key_id"] == "key"


def test_get_storage_gateway_falls_back_to_local_when_r2_creds_incomplete(
    monkeypatch, tmp_path: Path
):
    # Dev with STORAGE_BACKEND=r2 but no credentials yet -> local fallback so the
    # app keeps working until the user sets R2 secrets.
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path))
    settings = Settings(storage_backend="r2", environment="development")
    gateway = get_storage_gateway(settings)
    assert isinstance(gateway, LocalStorageGateway)


def test_get_storage_gateway_production_fail_closed_when_r2_incomplete():
    settings = Settings(storage_backend="r2", environment="production")
    gateway = get_storage_gateway(settings)
    assert isinstance(gateway, UnconfiguredStorageGateway)


@pytest.mark.asyncio
async def test_r2_presign_upload_returns_direct_put_url():
    with patch("boto3.client") as mock_client:
        s3 = MagicMock()
        s3.generate_presigned_url.return_value = "https://r2.example/signed-put"
        mock_client.return_value = s3
        gateway = R2StorageGateway(_r2_settings())

        presigned = await gateway.presign_upload(
            user_id="user-1", content_type="image/png", size_bytes=1024
        )
        assert presigned.api_upload is False  # client uploads directly to R2
        assert presigned.upload_url == "https://r2.example/signed-put"
        assert presigned.storage_key.startswith("user-1/")
        assert presigned.headers["Content-Type"] == "image/png"
        _, kwargs = s3.generate_presigned_url.call_args
        assert kwargs["Params"]["Key"] == presigned.storage_key
        assert kwargs["Params"]["ContentType"] == "image/png"


@pytest.mark.asyncio
async def test_r2_presign_download_returns_signed_get():
    with patch("boto3.client") as mock_client:
        s3 = MagicMock()
        s3.generate_presigned_url.return_value = "https://r2.example/signed-get"
        mock_client.return_value = s3
        gateway = R2StorageGateway(_r2_settings())

        url = await gateway.presign_download("user-1/abc")
        assert url == "https://r2.example/signed-get"
        args, kwargs = s3.generate_presigned_url.call_args
        assert args[0] == "get_object"  # ClientMethod, passed positionally via to_thread
        assert kwargs["Params"]["Key"] == "user-1/abc"


@pytest.mark.asyncio
async def test_r2_read_bytes_downloads_object():
    with patch("boto3.client") as mock_client:
        s3 = MagicMock()
        body = MagicMock()
        body.read.return_value = b"pdf bytes"
        s3.get_object.return_value = {"Body": body}
        mock_client.return_value = s3
        gateway = R2StorageGateway(_r2_settings())

        data = await gateway.read_bytes("user-1/abc")
        assert data == b"pdf bytes"


@pytest.mark.asyncio
async def test_r2_read_bytes_returns_none_on_failure():
    with patch("boto3.client") as mock_client:
        s3 = MagicMock()
        s3.get_object.side_effect = RuntimeError("no such key")
        mock_client.return_value = s3
        gateway = R2StorageGateway(_r2_settings())
        assert await gateway.read_bytes("user-1/missing") is None
