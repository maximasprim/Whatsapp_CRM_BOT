from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestDashboardStats:
    async def test_dashboard_returns_expected_structure(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/analytics/dashboard", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "customers" in data
        assert "leads" in data
        assert "revenue" in data
        assert "conversations" in data
        assert "tickets" in data

    async def test_dashboard_customer_counts_are_non_negative(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/analytics/dashboard", headers=auth_headers)
        data = resp.json()
        assert data["customers"]["total"] >= 0
        assert data["customers"]["active"] >= 0
        assert data["customers"]["new_this_month"] >= 0

    async def test_dashboard_returns_401_without_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/analytics/dashboard")
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestLeadFunnel:
    async def test_funnel_returns_list(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/analytics/leads/funnel", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "funnel" in data
        assert isinstance(data["funnel"], list)


@pytest.mark.asyncio
class TestCustomerGrowth:
    async def test_growth_returns_list_of_dated_counts(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/analytics/customers/growth?days=30", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "growth" in data
        assert isinstance(data["growth"], list)

    async def test_growth_returns_422_for_out_of_range_days(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/analytics/customers/growth?days=2", headers=auth_headers)
        assert resp.status_code == 422
