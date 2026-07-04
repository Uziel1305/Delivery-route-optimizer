"""End-to-end workflow against the live stack, exercising the REAL OSRM
routing engine for the time matrix. Coordinates are real Tel Aviv locations
so OSRM can snap them to the road network.
"""
from tests.integration.conftest import login, register_user, set_courier_locations

# Real Tel Aviv-area coordinates (lat, lon) so OSRM returns real travel times.
STOPS = [
    (32.0733, 34.7925),  # Florentin
    (32.1093, 34.8555),  # Ramat Gan
    (32.0684, 34.8248),  # Give'atayim
    (32.1000, 34.7806),  # north TLV
    (32.0567, 34.7607),  # Jaffa
]


def test_manager_courier_full_workflow(client, unique_suffix):
    mgr_name = f"mgr_{unique_suffix}"
    cour_name = f"cour_{unique_suffix}"

    register_user(client, mgr_name, "manager")
    courier = register_user(client, cour_name, "courier")
    courier_id = courier["id"]

    mgr = login(client, mgr_name)
    cour = login(client, cour_name)

    # Onboarding: set country
    r = client.patch("/users/me", json={"country": "il"}, headers=mgr)
    assert r.status_code == 200
    assert r.json()["country"] == "IL"

    # Courier onboarding: set start/end locations (applies instantly — no manager yet)
    r = set_courier_locations(client, cour)
    assert r["applied"] is True

    # Invite + accept
    r = client.post("/managers/me/invites", json={"courier_username": cour_name}, headers=mgr)
    assert r.status_code == 201
    invite_id = r.json()["id"]

    r = client.post(f"/couriers/me/invites/{invite_id}/accept", headers=cour)
    assert r.status_code == 200

    r = client.get("/managers/me/couriers", headers=mgr)
    assert r.status_code == 200
    assert any(c["id"] == courier_id for c in r.json())

    # Create job — courier start/end are copied from their profile (copy-on-assign)
    r = client.post(
        "/jobs",
        json={
            "delivery_date": "2026-07-06",
            "couriers": [
                {"courier_id": courier_id, "start_time_seconds": 0, "end_time_seconds": 10 * 3600}
            ],
        },
        headers=mgr,
    )
    assert r.status_code == 201
    job_id = r.json()["id"]
    assert r.json()["delivery_date"] == "2026-07-06"

    # Add stops
    for lat, lon in STOPS:
        r = client.post(
            f"/jobs/{job_id}/stops",
            json={"lat": lat, "lon": lon, "service_time_seconds": 120, "address_label": f"{lat},{lon}"},
            headers=mgr,
        )
        assert r.status_code == 201

    # Generate an option — this calls REAL OSRM for the time matrix.
    r = client.post(f"/jobs/{job_id}/options/generate", headers=mgr)
    assert r.status_code == 200, r.text
    option = r.json()
    assert option["feasible"] is True
    assert option["total_duration_seconds"] > 0  # real travel time, not zero
    option_id = option["id"]

    # All 5 stops should be assigned across the (single) courier's route.
    assigned = [s["job_stop_id"] for cr in option["courier_routes"] for s in cr["stops"]]
    assert len(assigned) == len(STOPS)
    assert len(set(assigned)) == len(STOPS)

    # Publish
    r = client.post(f"/jobs/{job_id}/options/{option_id}/publish", headers=mgr)
    assert r.status_code == 200
    assert r.json()["status"] == "published"

    # Courier reads own assignment — ordered, published-only.
    r = client.get("/couriers/me/assignments", headers=cour)
    assert r.status_code == 200
    stops = r.json()
    assert len(stops) == len(STOPS)
    sequences = [s["sequence_index"] for s in stops]
    assert sequences == sorted(sequences)

    r = client.get(f"/couriers/me/assignments/{job_id}", headers=cour)
    assert r.status_code == 200
    assert len(r.json()) == len(STOPS)


def test_authorization_boundary_other_courier_cannot_read(client, unique_suffix):
    mgr_name = f"mgr2_{unique_suffix}"
    cour_name = f"courA_{unique_suffix}"
    other_name = f"courB_{unique_suffix}"

    register_user(client, mgr_name, "manager")
    courier = register_user(client, cour_name, "courier")
    register_user(client, other_name, "courier")

    mgr = login(client, mgr_name)
    cour = login(client, cour_name)
    other = login(client, other_name)

    client.patch("/users/me", json={"country": "il"}, headers=mgr)
    set_courier_locations(client, cour)
    invite = client.post("/managers/me/invites", json={"courier_username": cour_name}, headers=mgr).json()
    client.post(f"/couriers/me/invites/{invite['id']}/accept", headers=cour)

    job_id = client.post(
        "/jobs",
        json={
            "delivery_date": "2026-07-06",
            "couriers": [
                {"courier_id": courier["id"], "start_time_seconds": 0, "end_time_seconds": 10 * 3600}
            ],
        },
        headers=mgr,
    ).json()["id"]

    for lat, lon in STOPS[:3]:
        client.post(
            f"/jobs/{job_id}/stops",
            json={"lat": lat, "lon": lon, "service_time_seconds": 60, "address_label": f"{lat},{lon}"},
            headers=mgr,
        )
    option = client.post(f"/jobs/{job_id}/options/generate", headers=mgr).json()
    client.post(f"/jobs/{job_id}/options/{option['id']}/publish", headers=mgr)

    # Unrelated courier: empty global list, 404 (not 403, not empty) for the specific job.
    r = client.get("/couriers/me/assignments", headers=other)
    assert r.status_code == 200
    assert r.json() == []

    r = client.get(f"/couriers/me/assignments/{job_id}", headers=other)
    assert r.status_code == 404


def test_manager_role_boundary(client, unique_suffix):
    cour_name = f"courC_{unique_suffix}"
    register_user(client, cour_name, "courier")
    cour = login(client, cour_name)

    # Courier hitting a manager-only route -> 403.
    r = client.post(
        "/jobs",
        json={"delivery_date": "2026-07-06", "couriers": []},
        headers=cour,
    )
    assert r.status_code == 403


def test_ui_read_endpoints(client, unique_suffix):
    """The list/detail endpoints the frontend depends on."""
    mgr_name = f"uimgr_{unique_suffix}"
    cour_name = f"uicour_{unique_suffix}"
    register_user(client, mgr_name, "manager")
    courier = register_user(client, cour_name, "courier")
    mgr = login(client, mgr_name)
    cour = login(client, cour_name)

    client.patch("/users/me", json={"country": "il"}, headers=mgr)
    set_courier_locations(client, cour)
    invite = client.post("/managers/me/invites", json={"courier_username": cour_name}, headers=mgr).json()
    client.post(f"/couriers/me/invites/{invite['id']}/accept", headers=cour)

    # Courier's manager lookup reflects the acceptance.
    r = client.get("/couriers/me/manager", headers=cour)
    assert r.status_code == 200
    assert r.json()["manager_username"] == mgr_name

    job_id = client.post(
        "/jobs",
        json={
            "delivery_date": "2026-07-06",
            "couriers": [
                {"courier_id": courier["id"], "start_time_seconds": 0, "end_time_seconds": 10 * 3600}
            ],
        },
        headers=mgr,
    ).json()["id"]

    for lat, lon in STOPS[:3]:
        client.post(
            f"/jobs/{job_id}/stops",
            json={"lat": lat, "lon": lon, "service_time_seconds": 60, "address_label": f"{lat},{lon}"},
            headers=mgr,
        )

    # Manager list/detail endpoints.
    jobs = client.get("/jobs", headers=mgr).json()
    summary = next(j for j in jobs if j["id"] == job_id)
    assert summary["stop_count"] == 3
    assert summary["courier_count"] == 1
    assert summary["delivery_date"] == "2026-07-06"

    detail = client.get(f"/jobs/{job_id}", headers=mgr).json()
    assert detail["delivery_date"] == "2026-07-06"
    assert len(client.get(f"/jobs/{job_id}/stops", headers=mgr).json()) == 3

    # The day carries the courier's copied start/end terminals.
    job_couriers = client.get(f"/jobs/{job_id}/couriers", headers=mgr).json()
    assert job_couriers[0]["username"] == cour_name
    assert "job_courier_id" in job_couriers[0]
    assert job_couriers[0]["start_address_label"] == "Courier start, central TLV"
    assert job_couriers[0]["end_address_label"] == "Courier end, central TLV"

    # Generate + publish, then the courier's job list should include it.
    option = client.post(f"/jobs/{job_id}/options/generate", headers=mgr).json()
    client.post(f"/jobs/{job_id}/options/{option['id']}/publish", headers=mgr)

    my_jobs = client.get("/couriers/me/jobs", headers=cour).json()
    assert any(j["job_id"] == job_id and j["stop_count"] == 3 for j in my_jobs)
