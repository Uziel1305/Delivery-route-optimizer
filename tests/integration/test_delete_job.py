"""Hard-deleting a job (UI: "delivery day"), including one with a published
option — the teardown has no FK cascades to lean on, so this exercises the
manual child-row deletion order end to end. Against the live stack.
"""
from tests.integration.conftest import login, register_user, set_courier_locations

STOPS = [
    (32.0733, 34.7925),  # Florentin
    (32.1093, 34.8555),  # Ramat Gan
    (32.0684, 34.8248),  # Give'atayim
]


def _create_job(client, mgr, courier_id):
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
    return r.json()["id"]


def test_delete_published_job_full_teardown(client, unique_suffix):
    mgr_name = f"delmgr_{unique_suffix}"
    cour_name = f"delcour_{unique_suffix}"
    register_user(client, mgr_name, "manager")
    courier = register_user(client, cour_name, "courier")
    mgr = login(client, mgr_name)
    cour = login(client, cour_name)

    client.patch("/users/me", json={"country": "il"}, headers=mgr)
    set_courier_locations(client, cour)
    invite = client.post("/managers/me/invites", json={"courier_username": cour_name}, headers=mgr).json()
    client.post(f"/couriers/me/invites/{invite['id']}/accept", headers=cour)

    job_id = _create_job(client, mgr, courier["id"])
    for lat, lon in STOPS:
        r = client.post(
            f"/jobs/{job_id}/stops",
            json={"lat": lat, "lon": lon, "service_time_seconds": 60, "address_label": f"{lat},{lon}"},
            headers=mgr,
        )
        assert r.status_code == 201

    option = client.post(f"/jobs/{job_id}/options/generate", headers=mgr).json()
    r = client.post(f"/jobs/{job_id}/options/{option['id']}/publish", headers=mgr)
    assert r.status_code == 200

    # Courier sees the published route before the delete.
    my_jobs = client.get("/couriers/me/jobs", headers=cour).json()
    assert any(j["job_id"] == job_id for j in my_jobs)

    r = client.delete(f"/jobs/{job_id}", headers=mgr)
    assert r.status_code == 204

    assert client.get(f"/jobs/{job_id}", headers=mgr).status_code == 404
    assert all(j["id"] != job_id for j in client.get("/jobs", headers=mgr).json())

    # Gone for the courier too.
    my_jobs = client.get("/couriers/me/jobs", headers=cour).json()
    assert all(j["job_id"] != job_id for j in my_jobs)
    assert client.get(f"/couriers/me/assignments/{job_id}", headers=cour).status_code == 404


def test_delete_job_authorization_and_draft(client, unique_suffix):
    owner_name = f"delown_{unique_suffix}"
    other_name = f"delothr_{unique_suffix}"
    cour_name = f"delcurb_{unique_suffix}"
    register_user(client, owner_name, "manager")
    register_user(client, other_name, "manager")
    courier = register_user(client, cour_name, "courier")
    owner = login(client, owner_name)
    other = login(client, other_name)
    cour = login(client, cour_name)

    client.patch("/users/me", json={"country": "il"}, headers=owner)
    set_courier_locations(client, cour)
    invite = client.post("/managers/me/invites", json={"courier_username": cour_name}, headers=owner).json()
    client.post(f"/couriers/me/invites/{invite['id']}/accept", headers=cour)

    # Draft job with no stops/options — the no-children teardown path.
    job_id = _create_job(client, owner, courier["id"])

    assert client.delete(f"/jobs/{job_id}", headers=other).status_code == 404
    assert client.delete(f"/jobs/{job_id}", headers=cour).status_code == 403
    assert client.get(f"/jobs/{job_id}", headers=owner).status_code == 200

    assert client.delete(f"/jobs/{job_id}", headers=owner).status_code == 204
    assert client.get(f"/jobs/{job_id}", headers=owner).status_code == 404
