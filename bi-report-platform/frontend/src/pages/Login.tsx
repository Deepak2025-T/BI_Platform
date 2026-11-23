import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { PRODUCT_NAME } from "../components/Brand";
import Icon from "../components/Icon";
import { AuthArt, TimusWordmark } from "../components/Timus";
import { errorMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";

/** What the product does, in the order somebody does it. Shown beside the sign-in card. */
const STEPS = [
  { icon: "database", label: "Connect data" },
  { icon: "chat", label: "Ask a question" },
  { icon: "spark", label: "AI builds it" },
  { icon: "reports", label: "Publish & share" },
];

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
        {/* The company's own shapes, cropped by the panel: the brand arrives before the form does. */}
        <span className="login-blob one" aria-hidden="true" />
        <span className="login-blob two" aria-hidden="true" />

        <div className="login-side-top">
          <TimusWordmark size={46} />
        </div>

        <AuthArt className="login-art" />

        <div className="login-side-foot">
          <h1 className="login-headline">Business Intelligence</h1>
          <ol className="login-steps">
            {STEPS.map((s, i) => (
              <li key={s.label}>
                <span className="login-step-ico">
                  <Icon name={s.icon} size={20} />
                  <b className="login-step-no">{i + 1}</b>
                </span>
                <span className="login-step-label">{s.label}</span>
              </li>
            ))}
          </ol>
        </div>
      </aside>

      <section className="login-main">
        <form className="login-card" onSubmit={onSubmit} noValidate>
          <div className="login-card-head">
            <TimusWordmark size={46} />
            <div className="login-card-product">
              <div className="strong">{PRODUCT_NAME}</div>
              <div className="muted small">Business Intelligence</div>
            </div>
          </div>

          <div>
            <h2 className="h1">Sign in</h2>
            <p className="muted small">Use your account to open {PRODUCT_NAME}.</p>
          </div>

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
              {/* An eye rather than the words, so the control takes the same room in every language
                  and never crowds a long password. */}
              <button type="button" className="pw-toggle icon" onClick={() => setShowPw((s) => !s)}
                aria-label={showPw ? "Hide password" : "Show password"} title={showPw ? "Hide password" : "Show password"}>
                <Icon name={showPw ? "eye-off" : "eye"} size={18} />
              </button>
            </div>
          </label>

          <button className="btn btn-primary btn-lg btn-block" type="submit" disabled={busy || !email || !password}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
          <p className="muted small c">Forgot your password? Ask a manager to reset it.</p>

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

        <p className="login-foot muted small">© {new Date().getFullYear()} Timus Consulting Services</p>
      </section>
    </div>
  );
}
