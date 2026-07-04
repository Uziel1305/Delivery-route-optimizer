import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { hhmmToSeconds, todayISO } from "../../utils/format";

/**
 * Single-step create flow: pick the delivery date, couriers, and their
 * per-job time windows. There is no depot — every courier drives from and
 * to their own start/end locations, which are copied onto the day at
 * creation (copy-on-assign). Couriers with no locations set can't be added.
 */
export default function CreateJobModal({ onClose, onCreated }) {
  const [deliveryDate, setDeliveryDate] = useState(todayISO());
  const [roster, setRoster] = useState([]);
  const [selected, setSelected] = useState({}); // courierId -> {start, end}
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.get("/managers/me/couriers").then(setRoster);
  }, []);

  function toggle(courierId) {
    setSelected((prev) => {
      const next = { ...prev };
      if (next[courierId]) delete next[courierId];
      else next[courierId] = { start: "08:00", end: "17:00" };
      return next;
    });
  }

  function setWindow(courierId, key, value) {
    setSelected((prev) => ({ ...prev, [courierId]: { ...prev[courierId], [key]: value } }));
  }

  async function createJob() {
    setError(null);
    setBusy(true);
    try {
      const couriers = Object.entries(selected).map(([courier_id, w]) => ({
        courier_id,
        start_time_seconds: hhmmToSeconds(w.start),
        end_time_seconds: hhmmToSeconds(w.end),
      }));
      const job = await api.post("/jobs", {
        delivery_date: deliveryDate,
        couriers,
      });
      onCreated(job.id);
    } catch {
      setError("Could not create job.");
      setBusy(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2 className="modal-title">New delivery day</h2>

        <div className="alert alert-info">
          Pick the delivery date, couriers, and their shift windows. Each courier's route starts and
          ends at their own saved locations.
        </div>
        {error && <div className="alert alert-error">{error}</div>}

        <div className="field">
          <label>Delivery date</label>
          <input
            className="input"
            type="date"
            value={deliveryDate}
            onChange={(e) => setDeliveryDate(e.target.value)}
            required
          />
        </div>

        {roster.length === 0 ? (
          <div className="empty">No couriers in your roster yet. Add some from the Couriers page first.</div>
        ) : (
          <div className="list" style={{ marginBottom: 16 }}>
            {roster.map((c) => {
              const sel = selected[c.id];
              const disabled = !c.has_locations;
              return (
                <div key={c.id} className="card" style={{ padding: 14, opacity: disabled ? 0.6 : 1 }}>
                  <label
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      cursor: disabled ? "not-allowed" : "pointer",
                    }}
                  >
                    <input type="checkbox" checked={!!sel} disabled={disabled} onChange={() => toggle(c.id)} />
                    <strong>{c.username}</strong>
                  </label>
                  {disabled && (
                    <div className="list-row-sub" style={{ marginTop: 6 }}>
                      No start/end locations set — set them on the Couriers page (or ask the courier) first.
                    </div>
                  )}
                  {!disabled && (
                    <div className="list-row-sub" style={{ marginTop: 6 }}>
                      {c.start_address_label} → {c.end_address_label}
                    </div>
                  )}
                  {sel && (
                    <div className="toolbar" style={{ marginTop: 10 }}>
                      <input
                        className="input"
                        type="time"
                        value={sel.start}
                        onChange={(e) => setWindow(c.id, "start", e.target.value)}
                      />
                      <span style={{ color: "#94a3b8" }}>to</span>
                      <input
                        className="input"
                        type="time"
                        value={sel.end}
                        onChange={(e) => setWindow(c.id, "end", e.target.value)}
                      />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        <div className="toolbar">
          <button className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button
            className="btn btn-primary"
            style={{ flex: 1 }}
            disabled={busy || Object.keys(selected).length === 0 || !deliveryDate}
            onClick={createJob}
          >
            {busy ? "Creating…" : "Create delivery day"}
          </button>
        </div>
      </div>
    </div>
  );
}
