import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { Icon } from "../../components/icons";

export default function InvitesPage() {
  const [invites, setInvites] = useState([]);
  const [manager, setManager] = useState({ manager_id: null, manager_username: null });
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState(null);

  async function load() {
    setLoading(true);
    const [inv, mgr] = await Promise.all([api.get("/couriers/me/invites"), api.get("/couriers/me/manager")]);
    setInvites(inv);
    setManager(mgr);
    setLoading(false);
  }

  useEffect(() => {
    load();
  }, []);

  async function respond(id, action) {
    await api.post(`/couriers/me/invites/${id}/${action}`);
    setNotice(action === "accept" ? "Invite accepted." : "Invite rejected.");
    await load();
  }

  async function leaveManager() {
    if (!confirm("Leave your current manager? You'll stop receiving their routes.")) return;
    await api.post("/couriers/me/leave-manager");
    setNotice("You've left your manager.");
    await load();
  }

  if (loading) return <div className="loading-center"><div className="spinner" /> Loading…</div>;

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Invites</h1>
          <div className="page-subtitle">Manage invitations and your current manager.</div>
        </div>
      </div>

      {notice && <div className="alert alert-success">{notice}</div>}

      <div className="card card-pad" style={{ marginBottom: 20 }}>
        <h3 style={{ marginBottom: 12 }}>Current manager</h3>
        {manager.manager_username ? (
          <div className="list-row" style={{ boxShadow: "none" }}>
            <div className="list-row-main">
              <div className="stop-index" style={{ background: "#4f46e5" }}>
                {manager.manager_username[0].toUpperCase()}
              </div>
              <div className="list-row-title">{manager.manager_username}</div>
            </div>
            <button className="btn btn-danger btn-sm" onClick={leaveManager}>
              Leave manager
            </button>
          </div>
        ) : (
          <div className="stat">You're not attached to any manager. Accept an invite below to join one.</div>
        )}
      </div>

      <h3 style={{ marginBottom: 12 }}>Pending invites</h3>
      {invites.length === 0 ? (
        <div className="card empty">
          <div className="empty-icon">📬</div>
          No pending invites.
        </div>
      ) : (
        <div className="list">
          {invites.map((inv) => (
            <div key={inv.id} className="list-row">
              <div className="list-row-main">
                <Icon.Mail />
                <div className="list-row-title">A manager invited you to their team</div>
              </div>
              <div className="row-actions">
                <button className="btn btn-success btn-sm" onClick={() => respond(inv.id, "accept")}>
                  <Icon.Check /> Accept
                </button>
                <button className="btn btn-ghost btn-sm" onClick={() => respond(inv.id, "reject")}>
                  Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
