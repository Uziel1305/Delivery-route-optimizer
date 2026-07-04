import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../api/client";
import { Icon } from "../components/icons";

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ username: "", email: "", password: "", role: "manager" });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const me = await register(form);
      if (me.role === "manager") navigate("/onboarding");
      else navigate("/courier/onboarding");
    } catch (err) {
      const detail = err instanceof ApiError ? err.detail : null;
      setError(typeof detail === "string" ? detail : "Registration failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="auth-brand">
          <Icon.Truck /> RouteOptim
        </div>
        <h1 className="auth-title">Create your account</h1>
        <p className="auth-sub">Choose how you'll use RouteOptim.</p>

        {error && <div className="alert alert-error">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="role-grid">
            <div
              className={`role-option ${form.role === "manager" ? "selected" : ""}`}
              onClick={() => setForm({ ...form, role: "manager" })}
            >
              <div className="role-icon">🧭</div>
              <div className="role-name">Manager</div>
              <div className="role-desc">Plan & assign routes</div>
            </div>
            <div
              className={`role-option ${form.role === "courier" ? "selected" : ""}`}
              onClick={() => setForm({ ...form, role: "courier" })}
            >
              <div className="role-icon">🚚</div>
              <div className="role-name">Courier</div>
              <div className="role-desc">Receive & drive routes</div>
            </div>
          </div>

          <div className="field">
            <label>Username</label>
            <input className="input" value={form.username} onChange={set("username")} autoFocus />
          </div>
          <div className="field">
            <label>Email</label>
            <input className="input" type="email" value={form.email} onChange={set("email")} />
          </div>
          <div className="field">
            <label>Password</label>
            <input className="input" type="password" value={form.password} onChange={set("password")} />
            <span style={{ fontSize: 12, color: "#94a3b8" }}>At least 8 characters.</span>
          </div>

          <button className="btn btn-primary btn-block" disabled={busy}>
            {busy ? "Creating account…" : "Create account"}
          </button>
        </form>

        <div className="auth-switch">
          Already have an account? <Link to="/login">Sign in</Link>
        </div>
      </div>
    </div>
  );
}
