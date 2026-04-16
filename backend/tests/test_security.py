from app.services.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hash_and_verify():
    h = hash_password("secret123")
    assert h != "secret123"
    assert verify_password("secret123", h) is True
    assert verify_password("wrong", h) is False


def test_verify_invalid_hash_returns_false():
    assert verify_password("whatever", "not-a-hash") is False


def test_token_roundtrip():
    token = create_access_token("user-id", {"email": "a@b.com"})
    payload = decode_token(token)
    assert payload["sub"] == "user-id"
    assert payload["email"] == "a@b.com"


def test_token_invalid_returns_none():
    assert decode_token("not.a.token") is None
