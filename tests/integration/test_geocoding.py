"""Geocoding integration tests against the live backend, which proxies the
real public Photon API. Network-dependent and tolerant of Photon flakiness:
they assert the proxy/auth wiring works, not exact OSM content.
"""
import httpx
import pytest

from tests.integration.conftest import login, register_user


@pytest.fixture
def manager_headers(client, unique_suffix):
    name = f"geomgr_{unique_suffix}"
    register_user(client, name, "manager")
    headers = login(client, name)
    client.patch("/users/me", json={"country": "il"}, headers=headers)
    return headers


def test_city_suggest_requires_country(client, unique_suffix):
    # A manager who hasn't onboarded (no country) must be blocked.
    name = f"nocountry_{unique_suffix}"
    register_user(client, name, "manager")
    headers = login(client, name)
    r = client.get("/geocoding/suggest/cities", params={"q": "Tel"}, headers=headers)
    assert r.status_code == 400


def test_city_suggest_requires_manager_role(client, unique_suffix):
    name = f"geocour_{unique_suffix}"
    register_user(client, name, "courier")
    headers = login(client, name)
    r = client.get("/geocoding/suggest/cities", params={"q": "Tel"}, headers=headers)
    assert r.status_code == 403


def test_city_suggest_returns_results(client, manager_headers):
    try:
        r = client.get("/geocoding/suggest/cities", params={"q": "Tel Aviv"}, headers=manager_headers, timeout=20.0)
    except httpx.HTTPError as exc:
        pytest.skip(f"Photon unreachable: {exc}")
    assert r.status_code == 200
    results = r.json()
    assert isinstance(results, list)
    if results:
        assert "lat" in results[0] and "lon" in results[0]


def test_validate_address_cascade(client, manager_headers):
    try:
        r = client.post(
            "/geocoding/validate",
            json={"city": "Tel Aviv", "street": "Rothschild Boulevard", "house_number": "1"},
            headers=manager_headers,
            timeout=20.0,
        )
    except httpx.HTTPError as exc:
        pytest.skip(f"Photon unreachable: {exc}")
    assert r.status_code == 200
    body = r.json()
    # Either valid with a coordinate, or invalid with a specific flagged field —
    # both prove the cascade ran end to end.
    assert "valid" in body
    if body["valid"]:
        assert body["coordinate"] is not None
    else:
        assert body["error"]["field"] in {"city", "street", "house_number"}
