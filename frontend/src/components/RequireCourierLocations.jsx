import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { api } from "../api/client";

/**
 * Couriers must have start/end locations before using the app ("required at
 * registration" — enforced right after sign-up, and retroactively for
 * accounts that predate per-courier locations). Redirects to the courier
 * onboarding flow until they're set.
 */
export default function RequireCourierLocations({ children }) {
  const [state, setState] = useState("loading"); // loading | ok | missing

  useEffect(() => {
    api
      .get("/couriers/me/locations")
      .then((loc) => setState(loc.has_locations ? "ok" : "missing"))
      .catch(() => setState("ok")); // fail open — the API enforces the hard rules
  }, []);

  if (state === "loading") return <div className="loading-center"><div className="spinner" /> Loading…</div>;
  if (state === "missing") return <Navigate to="/courier/onboarding" replace />;
  return children;
}
