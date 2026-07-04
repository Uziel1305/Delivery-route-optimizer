import { useEffect, useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api, ApiError } from "../../api/client";
import RouteMap, { ROUTE_COLORS } from "../../components/RouteMap";
import { Icon } from "../../components/icons";
import { formatDate, formatDateTime, formatDuration, statusBadgeClass } from "../../utils/format";

export default function JobDetailPage() {
  const { jobId } = useParams();
  const navigate = useNavigate();

  const [job, setJob] = useState(null);
  const [stops, setStops] = useState([]);
  const [couriers, setCouriers] = useState([]);
  const [options, setOptions] = useState([]);
  const [selectedOptionId, setSelectedOptionId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [nCouriers, setNCouriers] = useState("");
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [savedLocations, setSavedLocations] = useState([]);
  const [checkedLocationIds, setCheckedLocationIds] = useState({});
  const [addingFromLocations, setAddingFromLocations] = useState(false);

  const stopById = useMemo(() => Object.fromEntries(stops.map((s) => [s.id, s])), [stops]);
  const courierById = useMemo(
    () => Object.fromEntries(couriers.map((c) => [c.job_courier_id, c])),
    [couriers]
  );

  async function loadCore() {
    const [j, s, c, o] = await Promise.all([
      api.get(`/jobs/${jobId}`),
      api.get(`/jobs/${jobId}/stops`),
      api.get(`/jobs/${jobId}/couriers`),
      api.get(`/jobs/${jobId}/options`),
    ]);
    setJob(j);
    setStops(s);
    setCouriers(c);
    setOptions(o);
    setSelectedOptionId((prev) => {
      if (prev && o.some((x) => x.id === prev)) return prev;
      const active = o.find((x) => x.status === "published") || o.find((x) => x.status === "active") || o[0];
      return active ? active.id : null;
    });
  }

  useEffect(() => {
    (async () => {
      setLoading(true);
      await loadCore();
      setLoading(false);
    })();
    api.get("/locations").then(setSavedLocations);
  }, [jobId]);

  const selectedOption = options.find((o) => o.id === selectedOptionId) || null;

  function toggleLocation(id) {
    setCheckedLocationIds((prev) => ({ ...prev, [id]: !prev[id] }));
  }

  async function addFromSavedLocations() {
    const ids = Object.entries(checkedLocationIds)
      .filter(([, checked]) => checked)
      .map(([id]) => id);
    if (ids.length === 0) return;
    setAddingFromLocations(true);
    try {
      await api.post(`/jobs/${jobId}/stops/from-locations`, { location_ids: ids });
      setCheckedLocationIds({});
      await loadCore();
    } finally {
      setAddingFromLocations(false);
    }
  }

  async function deleteStop(stopId) {
    if (!confirm("Delete this stop? Active options will be regenerated.")) return;
    await api.delete(`/jobs/${jobId}/stops/${stopId}`);
    await loadCore();
  }

  async function generate() {
    setError(null);
    setNotice(null);
    setGenerating(true);
    try {
      const opt = await api.post(`/jobs/${jobId}/options/generate`);
      await loadCore();
      setSelectedOptionId(opt.id);
      setNotice("New option generated.");
    } catch (err) {
      const d = err instanceof ApiError ? err.detail : null;
      setError(typeof d === "string" ? d : "Could not generate a feasible option.");
    } finally {
      setGenerating(false);
    }
  }

  async function generateWithN(e) {
    e.preventDefault();
    setError(null);
    setNotice(null);
    setGenerating(true);
    try {
      const opt = await api.post(`/jobs/${jobId}/options/generate-with-n-couriers`, {
        courier_count: Number(nCouriers),
      });
      await loadCore();
      setSelectedOptionId(opt.id);
      setNotice(`Generated an option using ${nCouriers} courier(s).`);
      setNCouriers("");
    } catch (err) {
      const d = err instanceof ApiError ? err.detail : null;
      const msg = d && typeof d === "object" && d.message ? d.message : `Not feasible with ${nCouriers} courier(s).`;
      setError(msg + " Your existing options are unchanged.");
    } finally {
      setGenerating(false);
    }
  }

  async function swapStop(jobStopId, toJobCourierId) {
    setError(null);
    try {
      const updated = await api.post(`/jobs/${jobId}/options/${selectedOptionId}/swap`, {
        job_stop_id: jobStopId,
        to_job_courier_id: toJobCourierId,
      });
      await loadCore();
      setSelectedOptionId(updated.id);
    } catch (err) {
      const d = err instanceof ApiError ? err.detail : null;
      setError(typeof d === "string" ? d : "Swap didn't fit the courier's window.");
    }
  }

  async function publish() {
    setError(null);
    try {
      await api.post(`/jobs/${jobId}/options/${selectedOptionId}/publish`);
      await loadCore();
      setNotice("Option published — couriers can now see their routes.");
    } catch (err) {
      const d = err instanceof ApiError ? err.detail : null;
      setError(typeof d === "string" ? d : "Could not publish.");
    }
  }

  if (loading) return <div className="loading-center"><div className="spinner" /> Loading job…</div>;
  if (!job) return null;

  // Build map routes from the selected option.
  const mapRoutes = selectedOption
    ? selectedOption.courier_routes
        .filter((r) => r.stops.length > 0)
        .map((r, i) => ({
          color: ROUTE_COLORS[i % ROUTE_COLORS.length],
          label: courierById[r.job_courier_id]?.username || "Courier",
          stops: r.stops
            .map((s) => {
              const st = stopById[s.job_stop_id];
              return st ? { lat: st.lat, lon: st.lon, label: st.address_label, seq: s.sequence_index + 1 } : null;
            })
            .filter(Boolean),
        }))
    : [];

  const editable = selectedOption && selectedOption.status === "active";

  return (
    <>
      <div className="page-header">
        <div>
          <div className="toolbar" style={{ marginBottom: 6 }}>
            <button className="btn btn-ghost btn-sm" onClick={() => navigate("/manager/jobs")}>
              ← Delivery Days
            </button>
            <span className={statusBadgeClass(job.status)}>{job.status.replace("_", " ")}</span>
          </div>
          <h1>{formatDate(job.delivery_date)}</h1>
          <div className="page-subtitle">
            {stops.length} stops · {couriers.length} couriers assigned · #{job.id.slice(0, 8)}
          </div>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {notice && <div className="alert alert-success">{notice}</div>}

      <div className="split">
        {/* LEFT: stops + generation controls */}
        <div>
          <div className="card card-pad" style={{ marginBottom: 20 }}>
            <h3 style={{ marginBottom: 16 }}>Add from saved locations</h3>
            {savedLocations.length === 0 ? (
              <div className="empty" style={{ padding: 24 }}>
                No saved locations yet. Stops can only be added from your address book —
                <br />
                <button
                  className="btn btn-ghost btn-sm"
                  style={{ marginTop: 10 }}
                  onClick={() => navigate("/manager/locations")}
                >
                  Add delivery locations
                </button>
              </div>
            ) : (
              <>
                <div className="list" style={{ marginBottom: 12 }}>
                  {savedLocations.map((loc) => (
                    <label
                      key={loc.id}
                      style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}
                    >
                      <input
                        type="checkbox"
                        checked={!!checkedLocationIds[loc.id]}
                        onChange={() => toggleLocation(loc.id)}
                      />
                      {loc.address_label}
                    </label>
                  ))}
                </div>
                <button
                  className="btn btn-primary btn-block"
                  disabled={addingFromLocations || !Object.values(checkedLocationIds).some(Boolean)}
                  onClick={addFromSavedLocations}
                >
                  {addingFromLocations ? "Adding…" : "Add selected"}
                </button>
              </>
            )}
          </div>

          <div className="card card-pad" style={{ marginBottom: 20 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <h3>Stops ({stops.length})</h3>
            </div>
            {stops.length === 0 ? (
              <div className="empty" style={{ padding: 24 }}>No stops yet.</div>
            ) : (
              <div className="list">
                {stops.map((s) => (
                  <div key={s.id} className="stop-pill">
                    <Icon.Pin />
                    <div style={{ flex: 1 }}>
                      <div>{s.address_label}</div>
                      <div className="list-row-sub">Added {formatDateTime(s.created_at)}</div>
                    </div>
                    <button className="btn btn-danger btn-sm" onClick={() => deleteStop(s.id)}>
                      <Icon.Trash />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="card card-pad">
            <h3 style={{ marginBottom: 16 }}>Generate routes</h3>
            <button
              className="btn btn-primary btn-block"
              disabled={generating || stops.length === 0 || couriers.length === 0}
              onClick={generate}
              style={{ marginBottom: 12 }}
            >
              {generating ? "Optimizing…" : "Generate optimal split"}
            </button>
            <form onSubmit={generateWithN} className="toolbar">
              <input
                className="input"
                type="number"
                min="1"
                max={couriers.length}
                placeholder="Try with N couriers"
                value={nCouriers}
                onChange={(e) => setNCouriers(e.target.value)}
                style={{ flex: 1 }}
              />
              <button className="btn btn-ghost" disabled={generating || !nCouriers}>
                Try
              </button>
            </form>
            <div className="stat" style={{ marginTop: 8 }}>
              The optimizer minimizes total courier working time using live OSRM travel times.
            </div>
          </div>
        </div>

        {/* RIGHT: options + map */}
        <div>
          {options.length > 0 && (
            <div className="card card-pad" style={{ marginBottom: 20 }}>
              <h3 style={{ marginBottom: 16 }}>Options ({options.length})</h3>
              <div className="list">
                {options.map((o, idx) => (
                  <div
                    key={o.id}
                    className="list-row"
                    style={{
                      cursor: "pointer",
                      boxShadow: "none",
                      borderColor: o.id === selectedOptionId ? "var(--primary)" : "var(--border)",
                      background: o.id === selectedOptionId ? "var(--primary-soft)" : "#fff",
                    }}
                    onClick={() => setSelectedOptionId(o.id)}
                  >
                    <div className="list-row-main">
                      <div>
                        <div className="list-row-title">
                          Option {idx + 1}
                          {o.requested_courier_count ? ` · ${o.requested_courier_count} couriers` : ""}
                        </div>
                        <div className="list-row-sub">
                          {formatDuration(o.total_duration_seconds)} total ·{" "}
                          {o.courier_routes.filter((r) => r.stops.length).length} routes
                        </div>
                      </div>
                    </div>
                    <span className={statusBadgeClass(o.status)}>{o.status}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {selectedOption && (
            <>
              <RouteMap depot={{ lat: job.depot_lat, lon: job.depot_lon }} routes={mapRoutes} />

              <div style={{ marginTop: 20 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                  <h3>Routes</h3>
                  {editable && (
                    <button className="btn btn-success btn-sm" onClick={publish}>
                      <Icon.Check /> Publish
                    </button>
                  )}
                </div>

                {selectedOption.unassigned_stop_ids.length > 0 && (
                  <div className="alert alert-error">
                    {selectedOption.unassigned_stop_ids.length} stop(s) could not be assigned within courier windows.
                  </div>
                )}

                {selectedOption.courier_routes
                  .filter((r) => r.stops.length > 0)
                  .map((r, i) => {
                    const courier = courierById[r.job_courier_id];
                    const color = ROUTE_COLORS[i % ROUTE_COLORS.length];
                    const legsSum = r.stops.reduce((sum, s) => sum + s.leg_travel_seconds, 0);
                    const returnLegSeconds = Math.max(0, r.total_travel_seconds - legsSum);
                    return (
                      <div key={r.job_courier_id} className="route-group">
                        <div className="route-group-header">
                          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                            <span className="color-dot" style={{ background: color }} />
                            <strong>{courier?.username || "Courier"}</strong>
                          </div>
                          <div className="stat">
                            <strong>{formatDuration(r.total_duration_seconds)}</strong> · {r.stops.length} stops
                          </div>
                        </div>
                        <div className="route-group-body">
                          <div className="stop-pill" style={{ border: "none", padding: "4px 0" }}>
                            <span className="stop-index" style={{ background: "#0f172a" }}>★</span>
                            <div style={{ flex: 1 }}>
                              <strong>Depot</strong> <span className="stat">(start — can't be moved)</span>
                              {job.depot_address_label && <div className="stat">{job.depot_address_label}</div>}
                            </div>
                          </div>

                          {r.stops.map((s) => {
                            const st = stopById[s.job_stop_id];
                            return (
                              <div key={s.job_stop_id}>
                                <div className="route-leg">{formatDuration(s.leg_travel_seconds)} drive</div>
                                <div className="stop-pill" style={{ border: "none", padding: "4px 0" }}>
                                  <span className="stop-index" style={{ background: color }}>
                                    {s.sequence_index + 1}
                                  </span>
                                  <div style={{ flex: 1 }}>{st?.address_label || s.job_stop_id.slice(0, 8)}</div>
                                  {editable && couriers.length > 1 && (
                                    <select
                                      className="select"
                                      style={{ width: "auto", padding: "4px 8px", fontSize: 13 }}
                                      value=""
                                      onChange={(e) => e.target.value && swapStop(s.job_stop_id, e.target.value)}
                                    >
                                      <option value="">Move to…</option>
                                      {couriers
                                        .filter((c) => c.job_courier_id !== r.job_courier_id)
                                        .map((c) => (
                                          <option key={c.job_courier_id} value={c.job_courier_id}>
                                            {c.username}
                                          </option>
                                        ))}
                                    </select>
                                  )}
                                </div>
                              </div>
                            );
                          })}

                          <div className="route-leg">{formatDuration(returnLegSeconds)} drive</div>
                          <div className="stop-pill" style={{ border: "none", padding: "4px 0" }}>
                            <span className="stop-index" style={{ background: "#0f172a" }}>★</span>
                            <div style={{ flex: 1 }}>
                              <strong>Depot</strong> <span className="stat">(end — can't be moved)</span>
                              {job.depot_address_label && <div className="stat">{job.depot_address_label}</div>}
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}

                {!editable && selectedOption.status !== "published" && (
                  <div className="stat">This option is {selectedOption.status} and can't be edited. Generate a new one to make changes.</div>
                )}
              </div>
            </>
          )}

          {options.length === 0 && (
            <div className="card empty">
              <div className="empty-icon">🗺️</div>
              No options yet. Add stops, then generate an optimal split.
            </div>
          )}
        </div>
      </div>
    </>
  );
}
