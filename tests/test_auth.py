import pytest
from fastapi import HTTPException

from app.auth import hash_password, verify_password
from app.security import create_access_token, decode_access_token


def test_hash_password_is_not_plaintext():
    hashed = hash_password("secret123")
    assert hashed != "secret123"
    assert hashed.startswith("$2")  # bcrypt hashes start with $2


def test_verify_password_roundtrip():
    hashed = hash_password("secret123")
    assert verify_password("secret123", hashed) is True
    assert verify_password("wrongpass", hashed) is False


def test_jwt_roundtrip_contains_subject():
    token = create_access_token(subject="adnan@example.com")
    payload = decode_access_token(token)
    assert payload["sub"] == "adnan@example.com"


def test_expired_token_is_rejected():
    token = create_access_token(subject="adnan@example.com", expires_minutes=-1)
    with pytest.raises(HTTPException) as exc:
        decode_access_token(token)
    assert exc.value.status_code == 401
