from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestRegisterEndpoint:
    async def test_register_creates_user_and_returns_201(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "SecurePass123",
            "confirm_password": "SecurePass123",
            "first_name": "New",
            "last_name": "User",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "newuser@example.com"
        assert data["username"] == "newuser"
        assert "hashed_password" not in data

    async def test_register_returns_409_for_duplicate_email(self, client: AsyncClient):
        payload = {
            "email": "duplicate@example.com",
            "username": "user_one",
            "password": "SecurePass123",
            "confirm_password": "SecurePass123",
            "first_name": "First",
            "last_name": "User",
        }
        resp1 = await client.post("/api/v1/auth/register", json=payload)
        assert resp1.status_code == 201

        payload["username"] = "user_two"
        resp2 = await client.post("/api/v1/auth/register", json=payload)
        assert resp2.status_code == 409

    async def test_register_returns_422_when_passwords_do_not_match(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "mismatch@example.com",
            "username": "mismatch",
            "password": "SecurePass123",
            "confirm_password": "DifferentPass123",
            "first_name": "A",
            "last_name": "B",
        })
        assert resp.status_code == 422

    async def test_register_returns_422_when_password_has_no_uppercase(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "weak@example.com",
            "username": "weakpw",
            "password": "alllowercase123",
            "confirm_password": "alllowercase123",
            "first_name": "A",
            "last_name": "B",
        })
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestLoginEndpoint:
    async def test_login_returns_tokens_for_valid_credentials(self, client: AsyncClient, test_user):
        resp = await client.post("/api/v1/auth/login", json={
            "email": test_user.email,
            "password": "TestPassword123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

    async def test_login_returns_401_for_wrong_password(self, client: AsyncClient, test_user):
        resp = await client.post("/api/v1/auth/login", json={
            "email": test_user.email,
            "password": "WrongPassword999",
        })
        assert resp.status_code == 401

    async def test_login_returns_401_for_unknown_email(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "nobody@example.com",
            "password": "SomePassword123",
        })
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestMeEndpoint:
    async def test_get_me_returns_current_user(self, client: AsyncClient, test_user, auth_headers):
        resp = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == test_user.email
        assert data["username"] == test_user.username

    async def test_get_me_returns_401_without_token(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    async def test_get_me_returns_401_with_invalid_token(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalidtoken"})
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestPasswordChange:
    async def test_change_password_succeeds_with_correct_current_password(
        self, client: AsyncClient, test_user, auth_headers
    ):
        resp = await client.post("/api/v1/auth/change-password", headers=auth_headers, json={
            "current_password": "TestPassword123",
            "new_password": "NewSecure456",
            "confirm_password": "NewSecure456",
        })
        assert resp.status_code == 200

    async def test_change_password_returns_400_for_wrong_current_password(
        self, client: AsyncClient, test_user, auth_headers
    ):
        resp = await client.post("/api/v1/auth/change-password", headers=auth_headers, json={
            "current_password": "WrongCurrent123",
            "new_password": "NewSecure456",
            "confirm_password": "NewSecure456",
        })
        assert resp.status_code == 400
