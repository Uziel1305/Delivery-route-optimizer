"""Per-courier start/end locations: onboarding, the manager-consent change
flow, copy-on-assign into delivery days, and day-only edits. Against the
live stack (real Postgres, real OSRM for generation).
"""
from tests.integration.conftest import (
    DEFAULT_COURIER_LOCATIONS,
    login,
    register_user,
    set_courier_locations,
)

STOPS = [
    (32.0733, 34.7925),  # Florentin
    (32.1093, 34.8555),  # Ramat Gan
]

NEW_LOCATIONS = {
    "start_lat": 32.0567,
    "start_lon": 34.7607,
    "start_address_label": "New start, Jaffa",
    "end_lat": 32.1000,
    "end_lon": 34.7806,
    "end_address_label": "New end, north TLV",
}


def _pair(client, unique_suffix, tag):
    """Manager + affiliated courier (locations already set)."""
    mgr_name = f"lmgr{tag}_{unique_suffix}"
    cour_name = f"lcur{tag}_{unique_suffix}"
    register_user(client, mgr_name, "manager")
    courier = register_user(client, cour_name, "courier")
    mgr = login(client, mgr_name)
    cour = login(client, cour_name)
    client.patch("/users/me", json={"country": "il"}, headers=mgr)
    set_courier_locations(client, cour)
    invite = client.post("/managers/me/invites", json={"courier_username": cour_name}, headers=mgr).json()
    client.post(f"/couriers/me/invites/{invite['id']}/accept", headers=cour)
    return mgr, cour, courier


def test_unaffiliated_courier_edits_apply_instantly(client, unique_suffix):
    name = f"freecur_{unique_suffix}"
    register_user(client, name, "courier")
    cour = login(client, name)

    r = set_courier_locations(client, cour)
    assert r["applied"] is True

    r = set_courier_locations(client, cour, NEW_LOCATIONS)  # no manager -> still instant
    assert r["applied"] is True

    me = client.get("/couriers/me/locations", headers=cour).json()
    assert me["has_locations"] is True
    assert me["start_address_label"] == "New start, Jaffa"
    assert me["pending_request"] is None


def test_managed_courier_change_needs_approval(client, unique_suffix):
    mgr, cour, _ = _pair(client, unique_suffix, "a")

    # Change now goes through the approval queue.
    r = client.put("/couriers/me/locations", json=NEW_LOCATIONS, headers=cour)
    assert r.status_code == 200
    body = r.json()
    assert body["applied"] is False
    assert body["pending_request"]["status"] == "pending"

    # A second request while one is pending is rejected.
    assert client.put("/couriers/me/locations", json=NEW_LOCATIONS, headers=cour).status_code == 409

    # Manager sees it and approves; the profile updates.
    requests = client.get("/managers/me/location-requests", headers=mgr).json()
    assert len(requests) == 1
    req_id = requests[0]["id"]

    r = client.post(f"/managers/me/location-requests/{req_id}/approve", headers=mgr)
    assert r.status_code == 200

    me = client.get("/couriers/me/locations", headers=cour).json()
    assert me["start_address_label"] == "New start, Jaffa"
    assert me["pending_request"] is None


def test_declined_request_leaves_profile_untouched(client, unique_suffix):
    mgr, cour, _ = _pair(client, unique_suffix, "b")

    client.put("/couriers/me/locations", json=NEW_LOCATIONS, headers=cour)
    req_id = client.get("/managers/me/location-requests", headers=mgr).json()[0]["id"]
    client.post(f"/managers/me/location-requests/{req_id}/decline", headers=mgr)

    me = client.get("/couriers/me/locations", headers=cour).json()
    assert me["start_address_label"] == DEFAULT_COURIER_LOCATIONS["start_address_label"]
    assert me["pending_request"] is None


def test_job_creation_blocked_without_locations(client, unique_suffix):
    mgr_name = f"lmgrx_{unique_suffix}"
    cour_name = f"lcurx_{unique_suffix}"
    register_user(client, mgr_name, "manager")
    courier = register_user(client, cour_name, "courier")
    mgr = login(client, mgr_name)
    cour = login(client, cour_name)
    client.patch("/users/me", json={"country": "il"}, headers=mgr)
    invite = client.post("/managers/me/invites", json={"courier_username": cour_name}, headers=mgr).json()
    client.post(f"/couriers/me/invites/{invite['id']}/accept", headers=cour)

    r = client.post(
        "/jobs",
        json={
            "delivery_date": "2026-07-06",
            "couriers": [{"courier_id": courier["id"], "start_time_seconds": 0, "end_time_seconds": 36000}],
        },
        headers=mgr,
    )
    assert r.status_code == 422
    assert cour_name in r.json()["detail"]["couriers"]


def test_copy_on_assign_and_day_only_edit(client, unique_suffix):
    mgr, cour, courier = _pair(client, unique_suffix, "c")

    job_id = client.post(
        "/jobs",
        json={
            "delivery_date": "2026-07-06",
            "couriers": [{"courier_id": courier["id"], "start_time_seconds": 0, "end_time_seconds": 36000}],
        },
        headers=mgr,
    ).json()["id"]

    for lat, lon in STOPS:
        client.post(
            f"/jobs/{job_id}/stops",
            json={"lat": lat, "lon": lon, "service_time_seconds": 60, "address_label": f"{lat},{lon}"},
            headers=mgr,
        )

    jc = client.get(f"/jobs/{job_id}/couriers", headers=mgr).json()[0]
    assert jc["start_address_label"] == DEFAULT_COURIER_LOCATIONS["start_address_label"]

    # Manager edits the courier's DEFAULTS after the day was created — the
    # day's copy must not move (copy-on-assign).
    client.put(f"/managers/me/couriers/{courier['id']}/locations", json=NEW_LOCATIONS, headers=mgr)
    jc = client.get(f"/jobs/{job_id}/couriers", headers=mgr).json()[0]
    assert jc["start_address_label"] == DEFAULT_COURIER_LOCATIONS["start_address_label"]

    # Generate an option, then edit the day's copy — active options go stale.
    option = client.post(f"/jobs/{job_id}/options/generate", headers=mgr).json()
    assert option["status"] == "active"

    r = client.put(
        f"/jobs/{job_id}/couriers/{jc['job_courier_id']}/locations",
        json=NEW_LOCATIONS,
        headers=mgr,
    )
    assert r.status_code == 200
    assert r.json()["start_address_label"] == "New start, Jaffa"

    options = client.get(f"/jobs/{job_id}/options", headers=mgr).json()
    assert all(o["status"] == "stale" for o in options if o["id"] == option["id"])

    # Regeneration uses the day's new terminals and succeeds.
    regenerated = client.post(f"/jobs/{job_id}/options/generate", headers=mgr)
    assert regenerated.status_code == 200
    assert regenerated.json()["feasible"] is True
