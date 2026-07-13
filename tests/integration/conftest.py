"""Fixtures for integration tests that run against the LIVE docker-compose
stack over HTTP (real Postgres, real OSRM, real Celery). Unlike the unit
tests in tests/optimization/, these need `docker compose up` running —
including the `worker` service: route generation is dispatched to Celery
and tests poll until the worker finishes (see wait_for_option).

Run with:  API_BASE_URL=http://localhost:8000 pytest tests/integration -v
The whole suite auto-skips if the backend /health endpoint is unreachable.
"""
import os
import time
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


# Real Tel Aviv-area coordinates so OSRM can snap them to the road network.
DEFAULT_COURIER_LOCATIONS = {
    "start_lat": 32.0853,
    "start_lon": 34.7818,
    "start_address_label": "Courier start, central TLV",
    "end_lat": 32.0800,
    "end_lon": 34.7800,
    "end_address_label": "Courier end, central TLV",
}


def set_courier_locations(client: httpx.Client, headers: dict, locations: dict | None = None) -> dict:
    """Onboarding step: give a courier their default start/end terminals.
    Must run before the courier can be added to a delivery day.
    """
    resp = client.put("/couriers/me/locations", json=locations or DEFAULT_COURIER_LOCATIONS, headers=headers)
    resp.raise_for_status()
    return resp.json()


def wait_for_option(
    client: httpx.Client,
    headers: dict,
    job_id: str,
    option_id: str,
    timeout_seconds: float = 90.0,
) -> dict:
    """Poll until the Celery worker finishes a dispatched option (any
    terminal status: active/stale/failed). Fails the test on timeout —
    usually a sign the worker container isn't running."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        resp = client.get(f"/jobs/{job_id}/options/{option_id}", headers=headers)
        resp.raise_for_status()
        option = resp.json()
        if option["status"] != "pending":
            return option
        time.sleep(0.5)
    pytest.fail(
        f"option {option_id} still pending after {timeout_seconds}s — is the `worker` compose service running?"
    )
