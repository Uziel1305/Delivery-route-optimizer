import { useEffect, useState } from "react";
import { api, ApiError } from "../../api/client";
import { Icon } from "../../components/icons";

export default function RosterPage() {
  const [roster, setRoster] = useState([]);
  const [invites, setInvites] = useState([]);
  const [loading, setLoading] = useState(true);
  const [username, setUsername] = useState("");
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    setLoading(true);
    const [r, i] = await Promise.all([api.get("/managers/me/couriers"), api.get("/managers/me/invites")]);
    setRoster(r);
    setInvites(i);
    setLoading(false);
  }

  useEffect(() => {
    load();
  }, []);

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
              <input
                className="input"
                placeholder="Courier username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                style={{ flex: 1 }}
              />
              <button className="btn btn-primary" disabled={busy || !username}>
                <Icon.Plus /> Send invite
              </button>
            </form>
          </div>

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
                    </div>
                  </div>
                  <button className="btn btn-danger btn-sm" onClick={() => removeCourier(c.id)}>
                    <Icon.Trash /> Remove
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
