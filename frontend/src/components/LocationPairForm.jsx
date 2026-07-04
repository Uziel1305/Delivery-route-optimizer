import { useState } from "react";
import AddressForm from "./AddressForm";

/**
 * Collects a start + end location pair (each via the validated AddressForm),
 * with an "end is the same as start" shortcut. Calls
 * onSave({ start_lat, start_lon, start_address_label, end_lat, end_lon, end_address_label }).
 */
export default function LocationPairForm({ initial, onSave, busy, saveLabel = "Save locations" }) {
  const [start, setStart] = useState(initial?.start || null); // {lat, lon, label}
  const [end, setEnd] = useState(initial?.end || null);
  const [sameAsStart, setSameAsStart] = useState(false);

  const effectiveEnd = sameAsStart ? start : end;
  const ready = start && effectiveEnd;

  function save() {
    onSave({
      start_lat: start.lat,
      start_lon: start.lon,
      start_address_label: start.label,
      end_lat: effectiveEnd.lat,
      end_lon: effectiveEnd.lon,
      end_address_label: effectiveEnd.label,
    });
  }

  return (
    <div>
      <h3 style={{ marginBottom: 10 }}>Start location</h3>
      {start ? (
        <div className="alert alert-success" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
          <span>{start.label}</span>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setStart(null)}>
            Change
          </button>
        </div>
      ) : (
        <AddressForm submitLabel="Set start location" onResolved={(coord) => setStart(coord)} />
      )}

      <label style={{ display: "flex", alignItems: "center", gap: 8, margin: "14px 0", cursor: "pointer" }}>
        <input
          type="checkbox"
          checked={sameAsStart}
          onChange={(e) => setSameAsStart(e.target.checked)}
        />
        End location is the same as the start
      </label>

      {!sameAsStart && (
        <>
          <h3 style={{ marginBottom: 10 }}>End location</h3>
          {end ? (
            <div className="alert alert-success" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
              <span>{end.label}</span>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setEnd(null)}>
                Change
              </button>
            </div>
          ) : (
            <AddressForm submitLabel="Set end location" onResolved={(coord) => setEnd(coord)} />
          )}
        </>
      )}

      <button
        type="button"
        className="btn btn-primary btn-block"
        style={{ marginTop: 14 }}
        disabled={!ready || busy}
        onClick={save}
      >
        {busy ? "Saving…" : saveLabel}
      </button>
    </div>
  );
}
