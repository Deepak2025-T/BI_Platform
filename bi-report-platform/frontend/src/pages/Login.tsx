import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { errorMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState(params.get("expired") ? "Your session expired. Please sign in again." : "");
  const [busy, setBusy] = useState(false);

  const from = (location.state as { from?: string } | null)?.from || "/";
  if (user) return <Navigate to={from} replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(email, password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(errorMessage(err, "Couldn't sign in. Try again."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login">
      <aside className="login-side">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true"><span /><span /><span /></div>
          <div className="brand-name">BI Reports</div>
        </div>
        <div>
          <h1 className="login-headline">Ask a question. Get a report you can trust.</h1>
          <p className="login-copy">Every number shows the query and table it came from.</p>
        </div>
      </aside>

      <section className="login-main">
        <form className="login-form" onSubmit={onSubmit} noValidate>
          <h2 className="h1">Sign in</h2>
          {error && <div className="alert alert-error" role="alert">{error}</div>}

          <label className="field">
            <span>Work email</span>
            <input type="email" autoComplete="username" required value={email}
              onChange={(e) => setEmail(e.target.value)} autoFocus />
          </label>

          <label className="field">
            <span>Password</span>
            <div className="pw-wrap">
              <input type={showPw ? "text" : "password"} autoComplete="current-password" required
                value={password} onChange={(e) => setPassword(e.target.value)} />
              <button type="button" className="pw-toggle" onClick={() => setShowPw((s) => !s)}>
                {showPw ? "Hide" : "Show"}
              </button>
            </div>
          </label>

          <button className="btn btn-primary btn-lg" type="submit" disabled={busy || !email || !password}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
          <p className="muted small">Forgot your password? Ask a manager to reset it.</p>

          {import.meta.env.DEV && (
            <div className="demo-box">
              <div className="strong small">Demo accounts (development only)</div>
              <button type="button" className="link-btn" onClick={() => { setEmail("manager@example.com"); setPassword("Manager@123"); }}>
                Manager: manager@example.com
              </button>
              <button type="button" className="link-btn" onClick={() => { setEmail("user@example.com"); setPassword("User@123"); }}>
                User: user@example.com
              </button>
            </div>
          )}
        </form>
      </section>
    </div>
  );
}
