"""Manager address book: saved delivery locations, and quick-adding them as
stops on a job. Against the live stack (real Postgres).
"""
from tests.integration.conftest import login, register_user

DEPOT = (32.0853, 34.7818)

LOCATION_A = {"lat": 32.0733, "lon": 34.7925, "service_time_seconds": 90, "address_label": "Florentin 1"}
LOCATION_B = {"lat": 32.1093, "lon": 34.8555, "service_time_seconds": 60, "address_label": "Ramat Gan 1"}


def _manager_headers(client, unique_suffix, tag):
    name = f"locmgr_{tag}_{unique_suffix}"
    register_user(client, name, "manager")
    headers = login(client, name)
    client.patch("/users/me", json={"country": "il"}, headers=headers)
    return headers


def test_create_list_delete_saved_location(client, unique_suffix):
    mgr = _manager_headers(client, unique_suffix, "a")

    r = client.post("/locations", json=LOCATION_A, headers=mgr)
    assert r.status_code == 201
    loc_a = r.json()
    assert loc_a["address_label"] == "Florentin 1"

    r = client.post("/locations", json=LOCATION_B, headers=mgr)
    assert r.status_code == 201
    loc_b = r.json()

    # Ascending created_at order — oldest (first inserted) first.
    r = client.get("/locations", headers=mgr)
    assert r.status_code == 200
    ids_in_order = [loc["id"] for loc in r.json()]
    assert ids_in_order.index(loc_a["id"]) < ids_in_order.index(loc_b["id"])

    r = client.delete(f"/locations/{loc_a['id']}", headers=mgr)
    assert r.status_code == 204

    remaining = client.get("/locations", headers=mgr).json()
    assert loc_a["id"] not in [loc["id"] for loc in remaining]
    assert loc_b["id"] in [loc["id"] for loc in remaining]


def test_saved_location_ownership_boundary(client, unique_suffix):
    mgr_a = _manager_headers(client, unique_suffix, "b1")
    mgr_b = _manager_headers(client, unique_suffix, "b2")

    loc = client.post("/locations", json=LOCATION_A, headers=mgr_a).json()

    # Manager B cannot delete manager A's saved location.
    r = client.delete(f"/locations/{loc['id']}", headers=mgr_b)
    assert r.status_code == 404

    # It's still there for manager A.
    assert loc["id"] in [l["id"] for l in client.get("/locations", headers=mgr_a).json()]


def test_add_stops_from_saved_locations(client, unique_suffix):
    mgr = _manager_headers(client, unique_suffix, "c")

    loc_a = client.post("/locations", json=LOCATION_A, headers=mgr).json()
    loc_b = client.post("/locations", json=LOCATION_B, headers=mgr).json()

    job_id = client.post(
        "/jobs",
        json={
            "depot_lat": DEPOT[0],
            "depot_lon": DEPOT[1],
            "delivery_date": "2026-07-06",
            "couriers": [],
        },
        headers=mgr,
    ).json()["id"]

    r = client.post(
        f"/jobs/{job_id}/stops/from-locations",
        json={"location_ids": [loc_a["id"], loc_b["id"]]},
        headers=mgr,
    )
    assert r.status_code == 201
    created = r.json()
    assert len(created) == 2

    stops = client.get(f"/jobs/{job_id}/stops", headers=mgr).json()
    assert len(stops) == 2
    labels = {s["address_label"] for s in stops}
    assert labels == {"Florentin 1", "Ramat Gan 1"}
    coords = {(s["lat"], s["lon"]) for s in stops}
    assert (LOCATION_A["lat"], LOCATION_A["lon"]) in coords
    assert (LOCATION_B["lat"], LOCATION_B["lon"]) in coords

    # Each stop records when it was inserted, and the list is ordered by that.
    for s in stops:
        assert s["created_at"]
    assert stops == sorted(stops, key=lambda s: s["created_at"])


def test_add_stops_from_locations_ownership_boundary(client, unique_suffix):
    mgr_a = _manager_headers(client, unique_suffix, "d1")
    mgr_b = _manager_headers(client, unique_suffix, "d2")

    other_location = client.post("/locations", json=LOCATION_A, headers=mgr_b).json()

    job_id = client.post(
        "/jobs",
        json={
            "depot_lat": DEPOT[0],
            "depot_lon": DEPOT[1],
            "delivery_date": "2026-07-06",
            "couriers": [],
        },
        headers=mgr_a,
    ).json()["id"]

    # Manager A tries to quick-add manager B's saved location into their own job.
    r = client.post(
        f"/jobs/{job_id}/stops/from-locations",
        json={"location_ids": [other_location["id"]]},
        headers=mgr_a,
    )
    assert r.status_code == 404

    # No stop was created.
    assert client.get(f"/jobs/{job_id}/stops", headers=mgr_a).json() == []
