import { useEffect, useState } from "react";
import { api } from "../../api/client";
import AddressForm from "../../components/AddressForm";
import { Icon } from "../../components/icons";

export default function DeliveryLocationsPage() {
  const [locations, setLocations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState(null);

  async function load() {
    setLoading(true);
    setLocations(await api.get("/locations"));
    setLoading(false);
  }

  useEffect(() => {
    load();
  }, []);

  async function saveLocation(coord) {
    setSaving(true);
    try {
      await api.post("/locations", {
        lat: coord.lat,
        lon: coord.lon,
        service_time_seconds: 120,
        address_label: coord.label,
      });
      setNotice("Saved.");
      await load();
    } finally {
      setSaving(false);
    }
  }

  async function removeLocation(id) {
    if (!confirm("Remove this saved delivery location?")) return;
    await api.delete(`/locations/${id}`);
    await load();
  }

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Delivery Locations</h1>
          <div className="page-subtitle">
            Your reusable address book — save places once, then quickly add them to any delivery.
          </div>
        </div>
      </div>

      <div className="split">
        <div className="card card-pad">
          <h3 style={{ marginBottom: 16 }}>Add a delivery location</h3>
          {notice && <div className="alert alert-success">{notice}</div>}
          <AddressForm submitLabel="Save location" submitting={saving} onResolved={saveLocation} />
        </div>

        <div>
          <h3 style={{ marginBottom: 16 }}>Saved locations ({locations.length})</h3>
          {loading ? (
            <div className="loading-center"><div className="spinner" /> Loading…</div>
          ) : locations.length === 0 ? (
            <div className="card empty">
              <div className="empty-icon">📍</div>
              No saved locations yet. Add one to reuse it across deliveries.
            </div>
          ) : (
            <div className="list">
              {locations.map((loc) => (
                <div key={loc.id} className="stop-pill">
                  <Icon.Pin />
                  <div style={{ flex: 1 }}>{loc.address_label}</div>
                  <button className="btn btn-danger btn-sm" onClick={() => removeLocation(loc.id)}>
                    <Icon.Trash />
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
