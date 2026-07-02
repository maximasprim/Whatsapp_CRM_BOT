from __future__ import annotations

import pytest
from httpx import AsyncClient


VALID_CUSTOMER = {
    "first_name": "Alice",
    "last_name": "Wanjiru",
    "phone": "+254700000001",
    "email": "alice@example.com",
    "country": "Kenya",
    "city": "Nairobi",
}


@pytest.mark.asyncio
class TestCreateCustomer:
    async def test_creates_customer_and_returns_201(self, client: AsyncClient, auth_headers):
        resp = await client.post("/api/v1/customers", json=VALID_CUSTOMER, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["first_name"] == "Alice"
        assert data["phone"] == "+254700000001"
        assert "id" in data
        assert "hashed_password" not in data

    async def test_returns_401_without_authentication(self, client: AsyncClient):
        resp = await client.post("/api/v1/customers", json=VALID_CUSTOMER)
        assert resp.status_code == 401

    async def test_returns_409_for_duplicate_phone(self, client: AsyncClient, auth_headers):
        await client.post("/api/v1/customers", json=VALID_CUSTOMER, headers=auth_headers)
        resp2 = await client.post("/api/v1/customers", json={**VALID_CUSTOMER, "email": "other@example.com"}, headers=auth_headers)
        assert resp2.status_code == 409

    async def test_returns_422_for_missing_required_fields(self, client: AsyncClient, auth_headers):
        resp = await client.post("/api/v1/customers", json={"first_name": "Incomplete"}, headers=auth_headers)
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestListCustomers:
    async def test_returns_paginated_list(self, client: AsyncClient, auth_headers):
        for i in range(3):
            await client.post("/api/v1/customers", json={
                **VALID_CUSTOMER,
                "phone": f"+25470000{i:04d}",
                "email": f"user{i}@example.com",
            }, headers=auth_headers)

        resp = await client.get("/api/v1/customers?page=1&page_size=10", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data
        assert "page" in data
        assert data["total"] >= 3

    async def test_search_filters_by_name(self, client: AsyncClient, auth_headers):
        await client.post("/api/v1/customers", json={
            **VALID_CUSTOMER, "first_name": "UniqueSearchName", "phone": "+254799999999"
        }, headers=auth_headers)

        resp = await client.get("/api/v1/customers?search=UniqueSearchName", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert any("UniqueSearchName" in c["first_name"] for c in data["data"])


@pytest.mark.asyncio
class TestGetCustomer:
    async def test_returns_customer_by_id(self, client: AsyncClient, auth_headers):
        create_resp = await client.post("/api/v1/customers", json=VALID_CUSTOMER, headers=auth_headers)
        customer_id = create_resp.json()["id"]

        resp = await client.get(f"/api/v1/customers/{customer_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == customer_id

    async def test_returns_404_for_unknown_id(self, client: AsyncClient, auth_headers):
        import uuid
        resp = await client.get(f"/api/v1/customers/{uuid.uuid4()}", headers=auth_headers)
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestUpdateCustomer:
    async def test_updates_customer_fields(self, client: AsyncClient, auth_headers):
        create_resp = await client.post("/api/v1/customers", json=VALID_CUSTOMER, headers=auth_headers)
        customer_id = create_resp.json()["id"]

        resp = await client.put(f"/api/v1/customers/{customer_id}", json={"city": "Mombasa"}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["city"] == "Mombasa"


@pytest.mark.asyncio
class TestDeleteCustomer:
    async def test_deletes_customer_and_subsequent_get_returns_404(self, client: AsyncClient, auth_headers):
        create_resp = await client.post("/api/v1/customers", json={
            **VALID_CUSTOMER, "phone": "+254711000001"
        }, headers=auth_headers)
        customer_id = create_resp.json()["id"]

        del_resp = await client.delete(f"/api/v1/customers/{customer_id}", headers=auth_headers)
        assert del_resp.status_code == 200

        get_resp = await client.get(f"/api/v1/customers/{customer_id}", headers=auth_headers)
        assert get_resp.status_code == 404
