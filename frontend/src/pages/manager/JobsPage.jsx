import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { Icon } from "../../components/icons";
import { formatDate, statusBadgeClass } from "../../utils/format";
import CreateJobModal from "./CreateJobModal";

export default function JobsPage() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const navigate = useNavigate();

  async function load() {
    setLoading(true);
    setJobs(await api.get("/jobs"));
    setLoading(false);
  }

  useEffect(() => {
    load();
  }, []);

  function localTodayISO() {
    const now = new Date();
    const pad = (n) => String(n).padStart(2, "0");
    return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
  }

  async function deleteJob(job) {
    const dayPassed = job.delivery_date && job.delivery_date < localTodayISO();
    if (!dayPassed && !confirm("Delete this delivery day? Couriers will lose any published routes for it.")) {
      return;
    }
    await api.delete(`/jobs/${job.id}`);
    await load();
  }

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Delivery Days</h1>
          <div className="page-subtitle">Delivery days you've created.</div>
        </div>
        <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
          <Icon.Plus /> New delivery day
        </button>
      </div>

      {loading ? (
        <div className="loading-center"><div className="spinner" /> Loading…</div>
      ) : jobs.length === 0 ? (
        <div className="card empty">
          <div className="empty-icon">📦</div>
          No delivery days yet. Create your first one.
        </div>
      ) : (
        <div className="list">
          {jobs.map((job) => (
            <div
              key={job.id}
              className="list-row"
              style={{ cursor: "pointer" }}
              onClick={() => navigate(`/manager/jobs/${job.id}`)}
            >
              <div className="list-row-main">
                <div className="stop-index" style={{ background: "#0f172a" }}>
                  <Icon.Package width={16} height={16} />
                </div>
                <div>
                  <div className="list-row-title">{formatDate(job.delivery_date)}</div>
                  <div className="list-row-sub">
                    {job.stop_count} stops · {job.courier_count} couriers · #{job.id.slice(0, 8)}
                  </div>
                </div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span className={statusBadgeClass(job.status)}>{job.status.replace("_", " ")}</span>
                <button
                  className="btn btn-danger btn-sm"
                  title="Delete this delivery day"
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteJob(job);
                  }}
                >
                  <Icon.Trash />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {showCreate && (
        <CreateJobModal
          onClose={() => setShowCreate(false)}
          onCreated={(jobId) => {
            setShowCreate(false);
            navigate(`/manager/jobs/${jobId}`);
          }}
        />
      )}
    </>
  );
}
