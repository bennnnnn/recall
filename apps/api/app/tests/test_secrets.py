"""Tests for OAuth refresh-token encryption at rest."""

from cryptography.fernet import Fernet

from app.core.config import Settings
from app.core.secrets import decrypt_refresh_token, encrypt_refresh_token


def _settings_with_key() -> Settings:
    key = Fernet.generate_key().decode()
    return Settings(oauth_token_encryption_key=key, environment="development")


def test_encrypt_then_decrypt_round_trips():
    settings = _settings_with_key()
    token = "1//0gRT-example-refresh-token"
    cipher = encrypt_refresh_token(settings, token)
    assert cipher != token  # actually encrypted, not plaintext
    assert decrypt_refresh_token(settings, cipher) == token


def test_no_key_falls_back_to_plaintext():
    settings = Settings(oauth_token_encryption_key="", environment="development")
    token = "1//plain-token"
    assert encrypt_refresh_token(settings, token) == token
    assert decrypt_refresh_token(settings, token) == token


def test_decrypt_tolerates_legacy_plaintext():
    # Existing rows written before encryption hold plaintext Google tokens.
    # decrypt must return them unchanged so the rollout is non-breaking.
    settings = _settings_with_key()
    legacy = "1//0gRT-legacy-plaintext-token"
    assert decrypt_refresh_token(settings, legacy) == legacy


def test_empty_token_passthrough():
    settings = _settings_with_key()
    assert encrypt_refresh_token(settings, "") == ""
    assert decrypt_refresh_token(settings, "") == ""


def test_decrypt_wrong_key_treats_as_plaintext():
    # If the key is rotated and an old ciphertext can't be decrypted, return it
    # as-is rather than raising — the connection still fails closed at Google,
    # and we never crash the chat path over a token we can't read.
    key_a = Fernet.generate_key().decode()
    key_b = Fernet.generate_key().decode()
    cipher = encrypt_refresh_token(
        Settings(oauth_token_encryption_key=key_a, environment="development"),
        "1//secret",
    )
    out = decrypt_refresh_token(
        Settings(oauth_token_encryption_key=key_b, environment="development"),
        cipher,
    )
    assert out == cipher  # returned as-is, not the plaintext
