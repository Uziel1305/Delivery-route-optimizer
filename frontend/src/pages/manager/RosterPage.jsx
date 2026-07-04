import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../../api/client";
import LocationPairForm from "../../components/LocationPairForm";
import { Icon } from "../../components/icons";

export default function RosterPage() {
  const [roster, setRoster] = useState([]);
  const [invites, setInvites] = useState([]);
  const [locationRequests, setLocationRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [username, setUsername] = useState("");
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [busy, setBusy] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [editingCourier, setEditingCourier] = useState(null); // roster row being edited
  const [savingLocations, setSavingLocations] = useState(false);
  const suggestDebounce = useRef();

  async function load() {
    setLoading(true);
    const [r, i, lr] = await Promise.all([
      api.get("/managers/me/couriers"),
      api.get("/managers/me/invites"),
      api.get("/managers/me/location-requests"),
    ]);
    setRoster(r);
    setInvites(i);
    setLocationRequests(lr);
    setLoading(false);
  }

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    if (username.trim().length < 1) {
      setSuggestions([]);
      return;
    }
    clearTimeout(suggestDebounce.current);
    suggestDebounce.current = setTimeout(async () => {
      try {
        const res = await api.get(`/managers/me/courier-suggestions?q=${encodeURIComponent(username)}`);
        setSuggestions(res);
      } catch {
        setSuggestions([]);
      }
    }, 200);
    return () => clearTimeout(suggestDebounce.current);
  }, [username]);

  async function sendInvite(e) {
    e.preventDefault();
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      await api.post("/managers/me/invites", { courier_username: username });
      setNotice(`Invite sent to ${username}.`);
      setUsername("");
      await load();
    } catch (err) {
      const d = err instanceof ApiError ? err.detail : null;
      if (err.status === 404) setError("No courier found with that username.");
      else if (d === "courier_already_assigned") setError("That courier already belongs to a manager.");
      else if (typeof d === "string" && d.includes("pending")) setError("You already have a pending invite for that courier.");
      else setError("Could not send invite.");
    } finally {
      setBusy(false);
    }
  }

  async function removeCourier(courierId) {
    if (!confirm("Remove this courier from your roster?")) return;
    await api.delete(`/managers/me/couriers/${courierId}`);
    await load();
  }

  async function cancelInvite(id) {
    await api.delete(`/managers/me/invites/${id}`);
    await load();
  }

  async function resolveLocationRequest(id, action) {
    await api.post(`/managers/me/location-requests/${id}/${action}`);
    setNotice(action === "approve" ? "Location change approved." : "Location change declined.");
    await load();
  }

  async function saveCourierLocations(payload) {
    setSavingLocations(true);
    try {
      await api.put(`/managers/me/couriers/${editingCourier.id}/locations`, payload);
      setNotice(`Updated ${editingCourier.username}'s default locations.`);
      setEditingCourier(null);
      await load();
    } catch {
      setError("Could not update the courier's locations.");
    } finally {
      setSavingLocations(false);
    }
  }

  const pendingInvites = invites.filter((i) => i.status === "pending");

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Couriers</h1>
          <div className="page-subtitle">Invite couriers by username and manage your roster.</div>
        </div>
      </div>

      <div className="split">
        <div>
          <div className="card card-pad" style={{ marginBottom: 20 }}>
            <h3 style={{ marginBottom: 16 }}>Invite a courier</h3>
            {error && <div className="alert alert-error">{error}</div>}
            {notice && <div className="alert alert-success">{notice}</div>}
            <form onSubmit={sendInvite} className="toolbar">
              <div className="suggest-box" style={{ flex: 1 }}>
                <input
                  className="input"
                  placeholder="Courier username"
                  value={username}
                  onChange={(e) => {
                    setUsername(e.target.value);
                    setShowSuggestions(true);
                  }}
                  onFocus={() => setShowSuggestions(true)}
                  onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
                  autoComplete="off"
                />
                {showSuggestions && suggestions.length > 0 && (
                  <div className="suggest-list">
                    {suggestions.map((c) => (
                      <div
                        key={c.id}
                        className="suggest-item"
                        onMouseDown={() => {
                          setUsername(c.username);
                          setShowSuggestions(false);
                        }}
                      >
                        {c.username}
                        <span style={{ color: "#94a3b8" }}> · {c.email}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <button className="btn btn-primary" disabled={busy || !username}>
                <Icon.Plus /> Send invite
              </button>
            </form>
          </div>

          {locationRequests.length > 0 && (
            <div className="card card-pad" style={{ marginBottom: 20 }}>
              <h3 style={{ marginBottom: 16 }}>Location change requests</h3>
              <div className="list">
                {locationRequests.map((req) => (
                  <div key={req.id} className="card" style={{ padding: 14 }}>
                    <strong>{req.courier_username}</strong> wants to change their locations:
                    <div className="list-row-sub" style={{ margin: "8px 0" }}>
                      <div><strong>Start:</strong> {req.start_address_label}</div>
                      <div><strong>End:</strong> {req.end_address_label}</div>
                    </div>
                    <div className="toolbar">
                      <button
                        className="btn btn-primary btn-sm"
                        onClick={() => resolveLocationRequest(req.id, "approve")}
                      >
                        Approve
                      </button>
                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={() => resolveLocationRequest(req.id, "decline")}
                      >
                        Decline
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {pendingInvites.length > 0 && (
            <div className="card card-pad">
              <h3 style={{ marginBottom: 16 }}>Pending invites</h3>
              <div className="list">
                {pendingInvites.map((inv) => (
                  <div key={inv.id} className="list-row" style={{ boxShadow: "none" }}>
                    <div className="list-row-main">
                      <Icon.Mail />
                      <div className="list-row-sub">Waiting for courier to accept…</div>
                    </div>
                    <button className="btn btn-ghost btn-sm" onClick={() => cancelInvite(inv.id)}>
                      Cancel
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div>
          <h3 style={{ marginBottom: 16 }}>Your roster ({roster.length})</h3>
          {loading ? (
            <div className="loading-center"><div className="spinner" /> Loading…</div>
          ) : roster.length === 0 ? (
            <div className="card empty">
              <div className="empty-icon">👥</div>
              No couriers yet. Send an invite to get started.
            </div>
          ) : (
            <div className="list">
              {roster.map((c) => (
                <div key={c.id} className="list-row">
                  <div className="list-row-main">
                    <div className="stop-index" style={{ background: "#4f46e5" }}>
                      {c.username[0].toUpperCase()}
                    </div>
                    <div>
                      <div className="list-row-title">{c.username}</div>
                      <div className="list-row-sub">{c.email}</div>
                      <div className="list-row-sub">
                        {c.has_locations
                          ? `${c.start_address_label} → ${c.end_address_label}`
                          : "⚠ No start/end locations set"}
                      </div>
                    </div>
                  </div>
                  <div className="toolbar">
                    <button className="btn btn-ghost btn-sm" onClick={() => setEditingCourier(c)}>
                      <Icon.Pin /> Locations
                    </button>
                    <button className="btn btn-danger btn-sm" onClick={() => removeCourier(c.id)}>
                      <Icon.Trash /> Remove
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {editingCourier && (
        <div className="modal-overlay" onClick={() => setEditingCourier(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2 className="modal-title">{editingCourier.username} — default locations</h2>
            <div className="alert alert-info">
              These become the courier's defaults for future delivery days. Days already created keep
              their own copies. Any pending change request from the courier is cancelled.
            </div>
            <LocationPairForm
              onSave={saveCourierLocations}
              busy={savingLocations}
              saveLabel="Save defaults"
            />
            <button
              className="btn btn-ghost btn-block"
              style={{ marginTop: 8 }}
              onClick={() => setEditingCourier(null)}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </>
  );
}
