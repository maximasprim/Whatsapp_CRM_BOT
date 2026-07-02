from __future__ import annotations

import uuid
import pytest
from httpx import AsyncClient


async def _create_customer(client: AsyncClient, headers: dict, phone: str = "+254700000100") -> str:
    resp = await client.post("/api/v1/customers", json={
        "first_name": "Lead", "last_name": "TestCustomer", "phone": phone,
    }, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
class TestCreateLead:
    async def test_creates_lead_linked_to_customer(self, client: AsyncClient, auth_headers):
        cust_id = await _create_customer(client, auth_headers)
        resp = await client.post("/api/v1/leads", json={
            "title": "Enterprise Deal",
            "customer_id": cust_id,
            "estimated_value": 50000.0,
            "priority": "high",
            "source": "whatsapp",
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Enterprise Deal"
        assert data["customer_id"] == cust_id
        assert data["priority"] == "high"
        assert data["status"] == "new"

    async def test_returns_422_for_missing_customer_id(self, client: AsyncClient, auth_headers):
        resp = await client.post("/api/v1/leads", json={"title": "No Customer"}, headers=auth_headers)
        assert resp.status_code == 422

    async def test_returns_401_without_auth(self, client: AsyncClient):
        resp = await client.post("/api/v1/leads", json={"title": "Unauthenticated"})
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestListLeads:
    async def test_returns_paginated_list(self, client: AsyncClient, auth_headers):
        cust_id = await _create_customer(client, auth_headers, "+254700000101")
        for i in range(3):
            await client.post("/api/v1/leads", json={
                "title": f"Lead {i}", "customer_id": cust_id,
            }, headers=auth_headers)

        resp = await client.get("/api/v1/leads?page=1&page_size=20", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 3

    async def test_filter_by_status(self, client: AsyncClient, auth_headers):
        cust_id = await _create_customer(client, auth_headers, "+254700000102")
        await client.post("/api/v1/leads", json={
            "title": "New Lead", "customer_id": cust_id, "status": "new",
        }, headers=auth_headers)

        resp = await client.get("/api/v1/leads?status=new", headers=auth_headers)
        assert resp.status_code == 200
        for lead in resp.json()["data"]:
            assert lead["status"] == "new"


@pytest.mark.asyncio
class TestGetPipeline:
    async def test_pipeline_stats_returns_dict_with_counts(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/leads/pipeline", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)


@pytest.mark.asyncio
class TestUpdateLead:
    async def test_update_lead_status_to_qualified(self, client: AsyncClient, auth_headers):
        cust_id = await _create_customer(client, auth_headers, "+254700000103")
        create = await client.post("/api/v1/leads", json={
            "title": "Qualify Me", "customer_id": cust_id,
        }, headers=auth_headers)
        lead_id = create.json()["id"]

        resp = await client.put(f"/api/v1/leads/{lead_id}", json={"status": "qualified"}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "qualified"

    async def test_returns_404_for_unknown_lead(self, client: AsyncClient, auth_headers):
        resp = await client.put(f"/api/v1/leads/{uuid.uuid4()}", json={"status": "qualified"}, headers=auth_headers)
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestDeleteLead:
    async def test_delete_lead_and_confirm_404(self, client: AsyncClient, auth_headers):
        cust_id = await _create_customer(client, auth_headers, "+254700000104")
        create = await client.post("/api/v1/leads", json={
            "title": "Delete Me", "customer_id": cust_id,
        }, headers=auth_headers)
        lead_id = create.json()["id"]

        del_resp = await client.delete(f"/api/v1/leads/{lead_id}", headers=auth_headers)
        assert del_resp.status_code == 200

        get_resp = await client.get(f"/api/v1/leads/{lead_id}", headers=auth_headers)
        assert get_resp.status_code == 404
