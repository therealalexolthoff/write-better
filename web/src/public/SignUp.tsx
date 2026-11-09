// Teacher sign-up: name, email and password. Identity Platform creates the
// login and sends a verification email; then the API records the request
// for the admin to approve (api/app/signup.py). The new account can't do
// anything until approved.
import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError } from "../api";
import { authErrorMessage, teacherSignUp } from "../firebase";
import { PublicLayout } from "../Layout";
import { Link, PATHS, navigate } from "../router";

const MIN_PASSWORD = 12;

export default function SignUp({ signedIn }: { signedIn: boolean }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [website, setWebsite] = useState(""); // the hidden field: people never fill it in
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const submitting = useRef(false);

  // Already signed in (and not in the middle of signing up): nothing to do here.
  useEffect(() => {
    if (signedIn && !submitting.current) navigate(PATHS.app, { replace: true });
  }, [signedIn]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (password.length < MIN_PASSWORD) return setError(`Choose a password of at least ${MIN_PASSWORD} characters.`);
    submitting.current = true;
    setBusy(true);
    setError("");
    try {
      await teacherSignUp(name, email, password);
    } catch (err) {
      setError(authErrorMessage(err));
      setBusy(false);
      submitting.current = false;
      return;
    }
    try {
      await api("/signup", "POST", { name, website });
    } catch (err) {
      // The login exists; the waiting page lets them send the request again.
      if (err instanceof ApiError && err.status === 429) sessionStorage.setItem("signup-error", err.message);
    }
    navigate(PATHS.app, { replace: true });
  }

  return (
    <PublicLayout>
      <div className="auth-page">
        <section className="auth-card" aria-labelledby="sign-up-title">
          <h1 id="sign-up-title">Sign up as a teacher</h1>
          <p className="muted">
            Free for English teachers. The Write Better administrator approves each new teacher account before it can be
            used.
          </p>
          <form onSubmit={submit} className="stack">
            <label>
              Your name
              <input value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" maxLength={100} required />
            </label>
            <label>
              Email
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required />
              <span className="hint">We'll send a link to check it's yours.</span>
            </label>
            <label>
              Password
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
                minLength={MIN_PASSWORD}
                required
              />
              <span className="hint">At least {MIN_PASSWORD} characters.</span>
            </label>
            <div className="visually-hidden" aria-hidden="true">
              <label>
                Website
                <input tabIndex={-1} autoComplete="off" value={website} onChange={(e) => setWebsite(e.target.value)} />
              </label>
            </div>
            {error && <p className="error" role="alert">{error}</p>}
            <button className="primary big" disabled={busy}>{busy ? "Creating your account…" : "Sign up"}</button>
          </form>
        </section>
        <p className="auth-help muted">
          Already have an account? <Link to={PATHS.signIn}>Sign in</Link>
        </p>
      </div>
    </PublicLayout>
  );
}
