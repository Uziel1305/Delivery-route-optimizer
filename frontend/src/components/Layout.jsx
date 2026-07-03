import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { Icon } from "./icons";

export default function Layout() {
  const { user, logout } = useAuth();
  const isManager = user?.role === "manager";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <Icon.Truck />
          RouteOptim
        </div>

        {isManager ? (
          <>
            <NavLink to="/manager/jobs" className="nav-link">
              <Icon.Package /> Delivery Days
            </NavLink>
            <NavLink to="/manager/locations" className="nav-link">
              <Icon.Pin /> Delivery Locations
            </NavLink>
            <NavLink to="/manager/roster" className="nav-link">
              <Icon.Users /> Couriers
            </NavLink>
          </>
        ) : (
          <>
            <NavLink to="/courier/assignments" className="nav-link">
              <Icon.Map /> My Routes
            </NavLink>
            <NavLink to="/courier/invites" className="nav-link">
              <Icon.Mail /> Invites
            </NavLink>
          </>
        )}

        <div className="sidebar-footer">
          <div className="sidebar-user">
            <div className="username">{user?.username}</div>
            <div className="role">{user?.role}</div>
          </div>
          <button className="btn btn-ghost btn-block" onClick={logout} style={{ marginTop: 8 }}>
            <Icon.LogOut /> Sign out
          </button>
        </div>
      </aside>

      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
