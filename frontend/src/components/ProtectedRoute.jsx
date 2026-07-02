import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function ProtectedRoute({ role, children }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="loading-center">
        <div className="spinner" /> Loading…
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;

  // Managers must set a country before using the app (onboarding).
  if (user.role === "manager" && !user.country && window.location.pathname !== "/onboarding") {
    return <Navigate to="/onboarding" replace />;
  }

  if (role && user.role !== role) {
    const home = user.role === "manager" ? "/manager/jobs" : "/courier/assignments";
    return <Navigate to={home} replace />;
  }
  return children;
}
