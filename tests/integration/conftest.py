"""Fixtures for integration tests that run against the LIVE docker-compose
stack over HTTP (real Postgres, real OSRM, real Celery). Unlike the unit
tests in tests/optimization/, these need `docker compose up` running.

Run with:  API_BASE_URL=http://localhost:8000 pytest tests/integration -v
The whole suite auto-skips if the backend /health endpoint is unreachable.
"""
import os
import uuid

import httpx
import pytest

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")


def _stack_is_up() -> bool:
    try:
        resp = httpx.get(f"{API_BASE_URL}/health", timeout=3.0)
        return resp.status_code == 200
    except httpx.HTTPError:
        return False


pytestmark = pytest.mark.skipif(
    not _stack_is_up(),
    reason=f"live stack not reachable at {API_BASE_URL} (start it with `docker compose up`)",
)


@pytest.fixture(scope="session")
def client() -> httpx.Client:
    with httpx.Client(base_url=API_BASE_URL, timeout=30.0) as c:
        yield c


@pytest.fixture
def unique_suffix() -> str:
    # Tests share one persistent Postgres across runs; unique usernames avoid
    # collisions with rows left by earlier runs.
    return uuid.uuid4().hex[:8]


def register_user(client: httpx.Client, username: str, role: str) -> dict:
    resp = client.post(
        "/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "password123",
            "role": role,
        },
    )
    resp.raise_for_status()
    return resp.json()


def login(client: httpx.Client, username: str) -> dict:
    resp = client.post("/auth/login", json={"username": username, "password": "password123"})
    resp.raise_for_status()
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
