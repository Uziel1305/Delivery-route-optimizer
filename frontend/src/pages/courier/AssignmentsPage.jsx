import { useEffect, useState } from "react";
import { api } from "../../api/client";
import RouteMap, { ROUTE_COLORS } from "../../components/RouteMap";
import { Icon } from "../../components/icons";

export default function AssignmentsPage() {
  const [jobs, setJobs] = useState([]);
  const [selectedJobId, setSelectedJobId] = useState(null);
  const [stops, setStops] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingStops, setLoadingStops] = useState(false);

  useEffect(() => {
    (async () => {
      setLoading(true);
      const js = await api.get("/couriers/me/jobs");
      setJobs(js);
      if (js.length > 0) setSelectedJobId(js[0].job_id);
      setLoading(false);
    })();
  }, []);

  useEffect(() => {
    if (!selectedJobId) return;
    (async () => {
      setLoadingStops(true);
      try {
        const s = await api.get(`/couriers/me/assignments/${selectedJobId}`);
        setStops(s);
      } catch {
        setStops([]);
      } finally {
        setLoadingStops(false);
      }
    })();
  }, [selectedJobId]);

  if (loading) return <div className="loading-center"><div className="spinner" /> Loading…</div>;

  const selectedJob = jobs.find((j) => j.job_id === selectedJobId);
  const ordered = [...stops].sort((a, b) => a.sequence_index - b.sequence_index);

  const mapRoutes =
    selectedJob && ordered.length
      ? [
          {
            color: ROUTE_COLORS[0],
            label: "Your route",
            start:
              selectedJob.start_lat != null
                ? { lat: selectedJob.start_lat, lon: selectedJob.start_lon, label: selectedJob.start_address_label }
                : null,
            end:
              selectedJob.end_lat != null
                ? { lat: selectedJob.end_lat, lon: selectedJob.end_lon, label: selectedJob.end_address_label }
                : null,
            stops: ordered.map((s) => ({ lat: s.lat, lon: s.lon, label: s.address_label, seq: s.sequence_index + 1 })),
          },
        ]
      : [];

  return (
    <>
      <div className="page-header">
        <div>
          <h1>My Routes</h1>
          <div className="page-subtitle">Your published delivery assignments, in order.</div>
        </div>
      </div>

      {jobs.length === 0 ? (
        <div className="card empty">
          <div className="empty-icon">🗺️</div>
          No routes assigned yet. Once your manager publishes a plan, it'll appear here.
        </div>
      ) : (
        <div className="split">
          <div>
            <h3 style={{ marginBottom: 12 }}>Jobs ({jobs.length})</h3>
            <div className="list" style={{ marginBottom: 20 }}>
              {jobs.map((j) => (
                <div
                  key={j.job_id}
                  className="list-row"
                  style={{
                    cursor: "pointer",
                    borderColor: j.job_id === selectedJobId ? "var(--primary)" : "var(--border)",
                    background: j.job_id === selectedJobId ? "var(--primary-soft)" : "#fff",
                  }}
                  onClick={() => setSelectedJobId(j.job_id)}
                >
                  <div className="list-row-main">
                    <Icon.Package />
                    <div>
                      <div className="list-row-title">Job {j.job_id.slice(0, 8)}</div>
                      <div className="list-row-sub">{j.stop_count} stops</div>
                      {j.start_address_label && (
                        <div className="list-row-sub">
                          {j.start_address_label} → {j.end_address_label}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <h3 style={{ marginBottom: 12 }}>Stops in order</h3>
            {loadingStops ? (
              <div className="loading-center"><div className="spinner" /></div>
            ) : (
              <div className="list">
                {ordered.map((s) => (
                  <div key={s.job_stop_id} className="stop-pill">
                    <span className="stop-index">{s.sequence_index + 1}</span>
                    <div style={{ flex: 1 }}>{s.address_label}</div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div>
            {selectedJob && mapRoutes.length > 0 ? (
              <RouteMap routes={mapRoutes} />
            ) : (
              <div className="card empty">
                <div className="empty-icon">📍</div>
                Select a job to see the route.
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
