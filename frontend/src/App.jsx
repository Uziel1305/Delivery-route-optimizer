import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import Layout from "./components/Layout";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import OnboardingPage from "./pages/OnboardingPage";
import RosterPage from "./pages/manager/RosterPage";
import JobsPage from "./pages/manager/JobsPage";
import JobDetailPage from "./pages/manager/JobDetailPage";
import DeliveryLocationsPage from "./pages/manager/DeliveryLocationsPage";
import InvitesPage from "./pages/courier/InvitesPage";
import AssignmentsPage from "./pages/courier/AssignmentsPage";

function HomeRedirect() {
  const { user, loading } = useAuth();
  if (loading) return <div className="loading-center"><div className="spinner" /> Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={user.role === "manager" ? "/manager/jobs" : "/courier/assignments"} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route
        path="/onboarding"
        element={
          <ProtectedRoute role="manager">
            <OnboardingPage />
          </ProtectedRoute>
        }
      />

      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route
          path="/manager/jobs"
          element={
            <ProtectedRoute role="manager">
              <JobsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/manager/jobs/:jobId"
          element={
            <ProtectedRoute role="manager">
              <JobDetailPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/manager/roster"
          element={
            <ProtectedRoute role="manager">
              <RosterPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/manager/locations"
          element={
            <ProtectedRoute role="manager">
              <DeliveryLocationsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/courier/assignments"
          element={
            <ProtectedRoute role="courier">
              <AssignmentsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/courier/invites"
          element={
            <ProtectedRoute role="courier">
              <InvitesPage />
            </ProtectedRoute>
          }
        />
      </Route>

      <Route path="*" element={<HomeRedirect />} />
    </Routes>
  );
}
