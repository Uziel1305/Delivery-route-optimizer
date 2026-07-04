import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import LocationPairForm from "../../components/LocationPairForm";
import { Icon } from "../../components/icons";

// Same short list as the manager onboarding; OSRM routing itself is Israel-only.
const COUNTRIES = [
  { code: "IL", name: "Israel" },
  { code: "US", name: "United States" },
  { code: "GB", name: "United Kingdom" },
  { code: "DE", name: "Germany" },
  { code: "FR", name: "France" },
];

/**
 * Mandatory courier onboarding: country first (address search is scoped to
 * it), then the default start/end locations. Couriers can't use the app
 * until both are set — RequireCourierLocations redirects here.
 */
export default function CourierOnboardingPage() {
  const { user, refreshUser } = useAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState(user?.country ? 2 : 1);
  const [country, setCountry] = useState(user?.country || "IL");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function saveCountry(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.patch("/users/me", { country });
      await refreshUser();
      setStep(2);
    } finally {
      setBusy(false);
    }
  }

  async function saveLocations(payload) {
    setError(null);
    setBusy(true);
    try {
      await api.put("/couriers/me/locations", payload);
      navigate("/courier/assignments");
    } catch {
      setError("Could not save your locations. Please try again.");
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card" style={{ maxWidth: 480 }}>
        <div className="auth-brand">
          <Icon.Pin /> Almost there
        </div>

        {step === 1 && (
          <>
            <h1 className="auth-title">Where do you operate?</h1>
            <p className="auth-sub">We use this to scope address search to your country.</p>
            <form onSubmit={saveCountry}>
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
          </>
        )}

        {step === 2 && (
          <>
            <h1 className="auth-title">Your route start & end</h1>
            <p className="auth-sub">
              Every delivery day you're assigned starts at your start location and finishes at your end
              location (they can differ). Your manager plans routes around these.
            </p>
            {error && <div className="alert alert-error">{error}</div>}
            <LocationPairForm onSave={saveLocations} busy={busy} saveLabel="Finish setup" />
          </>
        )}
      </div>
    </div>
  );
}
