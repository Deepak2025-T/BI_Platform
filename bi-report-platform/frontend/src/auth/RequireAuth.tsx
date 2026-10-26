import type { ReactNode } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import type { Role } from "../api/types";
import { useAuth } from "./AuthContext";

/** Sends signed-out people to /login, and blocks pages their role can't open. */
export default function RequireAuth({ children, role }: { children: ReactNode; role?: Role }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <div className="center-screen">Loading…</div>;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;

  if (role === "manager" && user.role !== "manager") {
    return (
      <div className="page narrow">
        <h1 className="h1">You don't have access to this page</h1>
        <p className="muted">This page is for managers. Ask a manager if you need access.</p>
        <Link className="btn btn-primary" to="/">Back to home</Link>
      </div>
    );
  }
  return <>{children}</>;
}
