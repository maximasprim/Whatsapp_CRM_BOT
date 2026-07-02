from __future__ import annotations

import uuid
from datetime import timedelta

import pytest

from app.core.exceptions import ExpiredTokenException, InvalidTokenException
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    decrypt_value,
    encrypt_value,
    generate_otp,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_returns_different_string_from_input(self):
        plain = "MyPass123"
        hashed = hash_password(plain)
        assert hashed != plain
        assert len(hashed) > 20

    def test_verify_succeeds_with_correct_password(self):
        plain = "Correct99"
        assert verify_password(plain, hash_password(plain)) is True

    def test_verify_fails_with_wrong_password(self):
        hashed = hash_password("RightPass1")
        assert verify_password("WrongPass1", hashed) is False

    def test_same_password_produces_unique_hashes(self):
        plain = "SamePass1"
        h1 = hash_password(plain)
        h2 = hash_password(plain)
        assert h1 != h2
        assert verify_password(plain, h1) is True
        assert verify_password(plain, h2) is True


class TestJWTTokens:
    def test_access_token_round_trip(self):
        user_id = uuid.uuid4()
        token = create_access_token(subject=user_id)
        payload = decode_token(token, expected_type="access")
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "access"

    def test_refresh_token_round_trip(self):
        user_id = uuid.uuid4()
        token = create_refresh_token(subject=user_id)
        payload = decode_token(token, expected_type="refresh")
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "refresh"

    def test_access_token_rejected_as_refresh(self):
        token = create_access_token(subject=uuid.uuid4())
        with pytest.raises(InvalidTokenException):
            decode_token(token, expected_type="refresh")

    def test_expired_token_raises_expired_exception(self):
        token = create_access_token(subject=uuid.uuid4(), expires_delta=timedelta(seconds=-1))
        with pytest.raises(ExpiredTokenException):
            decode_token(token, expected_type="access")

    def test_tampered_token_raises_invalid_exception(self):
        token = create_access_token(subject=uuid.uuid4())
        tampered = token[:-5] + "xxxxx"
        with pytest.raises(InvalidTokenException):
            decode_token(tampered, expected_type="access")

    def test_token_carries_extra_claims(self):
        user_id = uuid.uuid4()
        token = create_access_token(subject=user_id, extra_claims={"email": "t@t.com", "is_superuser": True})
        payload = decode_token(token, expected_type="access")
        assert payload["email"] == "t@t.com"
        assert payload["is_superuser"] is True


class TestEncryption:
    def test_encrypt_decrypt_round_trip(self):
        original = "sensitive-oauth-token"
        encrypted = encrypt_value(original)
        assert encrypted != original
        assert decrypt_value(encrypted) == original

    def test_encrypted_values_are_non_deterministic(self):
        original = "same-value"
        enc1 = encrypt_value(original)
        enc2 = encrypt_value(original)
        assert enc1 != enc2
        assert decrypt_value(enc1) == original
        assert decrypt_value(enc2) == original


class TestOTPGeneration:
    def test_default_length_is_six_digits(self):
        otp = generate_otp()
        assert len(otp) == 6
        assert otp.isdigit()

    def test_custom_length_is_respected(self):
        assert len(generate_otp(length=4)) == 4

    def test_values_are_randomized(self):
        otps = {generate_otp() for _ in range(20)}
        assert len(otps) > 1
