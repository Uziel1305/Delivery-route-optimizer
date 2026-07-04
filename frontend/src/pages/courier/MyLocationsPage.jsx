import { useEffect, useState } from "react";
import { api, ApiError } from "../../api/client";
import LocationPairForm from "../../components/LocationPairForm";
import { Icon } from "../../components/icons";

/**
 * Courier's default start/end locations. Unaffiliated couriers edit freely;
 * managed couriers submit a change request that their manager must approve.
 */
export default function MyLocationsPage() {
  const [locations, setLocations] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  async function load() {
    setLoading(true);
    setLocations(await api.get("/couriers/me/locations"));
    setLoading(false);
  }

  useEffect(() => {
    load();
  }, []);

  async function save(payload) {
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      const res = await api.put("/couriers/me/locations", payload);
      setNotice(
        res.applied
          ? "Locations updated."
          : "Change request sent — it will apply once your manager approves it."
      );
      setEditing(false);
      await load();
    } catch (err) {
      const d = err instanceof ApiError ? err.detail : null;
      setError(typeof d === "string" ? d : "Could not save the change.");
    } finally {
      setBusy(false);
    }
  }

  async function cancelPending() {
    await api.delete("/couriers/me/locations/pending");
    setNotice("Change request cancelled.");
    await load();
  }

  if (loading) return <div className="loading-center"><div className="spinner" /> Loading…</div>;

  return (
    <>
      <div className="page-header">
        <div>
          <h1>My Locations</h1>
          <div className="page-subtitle">
            Where your delivery routes start and end. Changes need your manager's approval (if you have one).
          </div>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {notice && <div className="alert alert-success">{notice}</div>}

      <div className="split">
        <div>
          <div className="card card-pad" style={{ marginBottom: 20 }}>
            <h3 style={{ marginBottom: 16 }}>Current locations</h3>
            <div className="stop-pill" style={{ marginBottom: 8 }}>
              <Icon.Pin />
              <div style={{ flex: 1 }}>
                <div className="list-row-sub">Start</div>
                <div>{locations.start_address_label || "—"}</div>
              </div>
            </div>
            <div className="stop-pill">
              <Icon.Pin />
              <div style={{ flex: 1 }}>
                <div className="list-row-sub">End</div>
                <div>{locations.end_address_label || "—"}</div>
              </div>
            </div>
            {!editing && !locations.pending_request && (
              <button className="btn btn-primary btn-block" style={{ marginTop: 14 }} onClick={() => setEditing(true)}>
                Change locations
              </button>
            )}
          </div>

          {locations.pending_request && (
            <div className="card card-pad">
              <h3 style={{ marginBottom: 12 }}>Pending change request</h3>
              <div className="alert alert-info">
                Waiting for your manager to approve:
                <div style={{ marginTop: 8 }}>
                  <strong>Start:</strong> {locations.pending_request.start_address_label}
                </div>
                <div>
                  <strong>End:</strong> {locations.pending_request.end_address_label}
                </div>
              </div>
              <button className="btn btn-ghost btn-block" onClick={cancelPending}>
                Cancel request
              </button>
            </div>
          )}
        </div>

        <div>
          {editing && (
            <div className="card card-pad">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <h3>New locations</h3>
                <button className="btn btn-ghost btn-sm" onClick={() => setEditing(false)}>
                  Cancel
                </button>
              </div>
              <LocationPairForm onSave={save} busy={busy} saveLabel="Submit change" />
            </div>
          )}
        </div>
      </div>
    </>
  );
}
