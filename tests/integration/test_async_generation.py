"""Async generation via Celery: PENDING placeholder options, FAILED options
with error_detail, and the dismiss endpoint. Requires the live stack
INCLUDING the `worker` compose service.
"""
from tests.integration.conftest import login, register_user, set_courier_locations, wait_for_option

STOPS = [
    (32.0733, 34.7925),  # Florentin
    (32.1093, 34.8555),  # Ramat Gan
    (32.0684, 34.8248),  # Give'atayim
]

# A courier whose shift is 60 seconds can't serve anything — guaranteed
# infeasible regardless of OSRM travel times.
IMPOSSIBLE_WINDOW = {"start_time_seconds": 0, "end_time_seconds": 60}
NORMAL_WINDOW = {"start_time_seconds": 0, "end_time_seconds": 10 * 3600}


def _setup_day(client, suffix, window):
    mgr_name = f"agmgr_{suffix}"
    cour_name = f"agcour_{suffix}"
    register_user(client, mgr_name, "manager")
    courier = register_user(client, cour_name, "courier")
    mgr = login(client, mgr_name)
    cour = login(client, cour_name)
    client.patch("/users/me", json={"country": "il"}, headers=mgr)
    set_courier_locations(client, cour)
    invite = client.post("/managers/me/invites", json={"courier_username": cour_name}, headers=mgr).json()
    client.post(f"/couriers/me/invites/{invite['id']}/accept", headers=cour)

    job_id = client.post(
        "/jobs",
        json={"delivery_date": "2026-07-20", "couriers": [{"courier_id": courier["id"], **window}]},
        headers=mgr,
    ).json()["id"]
    for lat, lon in STOPS:
        client.post(
            f"/jobs/{job_id}/stops",
            json={"lat": lat, "lon": lon, "service_time_seconds": 120, "address_label": f"{lat},{lon}"},
            headers=mgr,
        )
    return mgr, job_id


def test_generate_returns_pending_then_active(client, unique_suffix):
    mgr, job_id = _setup_day(client, unique_suffix, NORMAL_WINDOW)

    r = client.post(f"/jobs/{job_id}/options/generate", headers=mgr)
    assert r.status_code == 200, r.text
    pending = r.json()
    assert pending["status"] == "pending"
    assert pending["courier_routes"] == []

    option = wait_for_option(client, mgr, job_id, pending["id"])
    assert option["status"] == "active"
    assert option["error_detail"] is None
    assert option["total_duration_seconds"] > 0
    # Job status flips only when the worker finishes successfully.
    assert client.get(f"/jobs/{job_id}", headers=mgr).json()["status"] == "options_ready"


def test_infeasible_generation_lands_as_failed_with_reason(client, unique_suffix):
    mgr, job_id = _setup_day(client, f"inf{unique_suffix[:5]}", IMPOSSIBLE_WINDOW)

    pending = client.post(f"/jobs/{job_id}/options/generate", headers=mgr).json()
    option = wait_for_option(client, mgr, job_id, pending["id"])
    assert option["status"] == "failed"
    assert "infeasible" in option["error_detail"]
    # A failed solve must not flip the day's status.
    assert client.get(f"/jobs/{job_id}", headers=mgr).json()["status"] == "draft"


def test_dismiss_failed_option_only(client, unique_suffix):
    mgr, job_id = _setup_day(client, f"dis{unique_suffix[:5]}", NORMAL_WINDOW)

    # Out-of-range N fails fast in the request, no option row created.
    r = client.post(f"/jobs/{job_id}/options/generate-with-n-couriers", json={"courier_count": 5}, headers=mgr)
    assert r.status_code == 422

    # A valid N=1 succeeds end-to-end.
    pending = client.post(
        f"/jobs/{job_id}/options/generate-with-n-couriers", json={"courier_count": 1}, headers=mgr
    ).json()
    active = wait_for_option(client, mgr, job_id, pending["id"])
    assert active["status"] == "active"
    assert active["requested_courier_count"] == 1

    # ACTIVE options cannot be dismissed.
    r = client.delete(f"/jobs/{job_id}/options/{active['id']}", headers=mgr)
    assert r.status_code == 409

    # Make a FAILED option (impossible window via the day-locations edit is
    # complex; simplest is a second day) — reuse the infeasible setup.
    mgr2, job2 = _setup_day(client, f"dsf{unique_suffix[:5]}", IMPOSSIBLE_WINDOW)
    pending = client.post(f"/jobs/{job2}/options/generate", headers=mgr2).json()
    failed = wait_for_option(client, mgr2, job2, pending["id"])
    assert failed["status"] == "failed"

    r = client.delete(f"/jobs/{job2}/options/{failed['id']}", headers=mgr2)
    assert r.status_code == 204
    assert client.get(f"/jobs/{job2}/options/{failed['id']}", headers=mgr2).status_code == 404
