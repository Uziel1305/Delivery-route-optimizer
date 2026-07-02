import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Icon } from "../components/icons";

// A short list is enough for the project; OSRM routing itself is Israel-only.
const COUNTRIES = [
  { code: "IL", name: "Israel" },
  { code: "US", name: "United States" },
  { code: "GB", name: "United Kingdom" },
  { code: "DE", name: "Germany" },
  { code: "FR", name: "France" },
];

export default function OnboardingPage() {
  const { refreshUser } = useAuth();
  const navigate = useNavigate();
  const [country, setCountry] = useState("IL");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.patch("/users/me", { country });
      await refreshUser();
      navigate("/manager/jobs");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="auth-brand">
          <Icon.Pin /> One last thing
        </div>
        <h1 className="auth-title">Where do you operate?</h1>
        <p className="auth-sub">
          We use this to scope address search to your country. (Live routing is available for Israel.)
        </p>
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label>Country</label>
            <select className="select" value={country} onChange={(e) => setCountry(e.target.value)}>
              {COUNTRIES.map((c) => (
                <option key={c.code} value={c.code}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
          <button className="btn btn-primary btn-block" disabled={busy}>
            {busy ? "Saving…" : "Continue"}
          </button>
        </form>
      </div>
    </div>
  );
}
