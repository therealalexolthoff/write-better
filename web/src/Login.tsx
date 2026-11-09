// The sign-in page: students (username and password) or staff, meaning
// teachers and the admin (email, password, then the authenticator code).
// App.tsx moves to the signed-in app once Identity Platform reports a session.
import { useState, type FormEvent } from "react";
import type { MultiFactorResolver } from "firebase/auth";
import { studentSignIn, teacherCodeStep, teacherPasswordStep } from "./firebase";
import { PublicLayout } from "./Layout";

type Mode = "student" | "staff";

export default function Login() {
  const [mode, setMode] = useState<Mode>("student");
  return (
    <PublicLayout>
      <div className="auth-page">
        <section className="auth-card" aria-labelledby="sign-in-title">
          <h1 id="sign-in-title">Sign in</h1>
          <div className="segmented" role="tablist" aria-label="Who is signing in">
            <button role="tab" aria-selected={mode === "student"} className={mode === "student" ? "active" : ""} onClick={() => setMode("student")}>
              Student
            </button>
            <button role="tab" aria-selected={mode === "staff"} className={mode === "staff" ? "active" : ""} onClick={() => setMode("staff")}>
              Teacher or admin
            </button>
          </div>
          {mode === "student" ? <StudentLogin /> : <StaffLogin />}
        </section>
        <p className="auth-help muted">
          {mode === "student"
            ? "Forgot your password? Ask your teacher to reset it."
            : "Forgot your password or lost your authenticator app? Ask the Write Better administrator."}
        </p>
      </div>
    </PublicLayout>
  );
}

function StudentLogin() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await studentSignIn(username, password);
    } catch {
      setError("That username or password didn't work. Check them and try again.");
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="stack">
      <label>
        Username
        <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" autoCapitalize="none" required />
        <span className="hint">The name your teacher gave you, for example maria.k</span>
      </label>
      <label>
        Password
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
      </label>
      {error && <p className="error" role="alert">{error}</p>}
      <button className="primary big" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
    </form>
  );
}

function StaffLogin() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [resolver, setResolver] = useState<MultiFactorResolver | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (resolver) {
        await teacherCodeStep(resolver, code);
      } else {
        setResolver(await teacherPasswordStep(email, password));
        setBusy(false);
      }
    } catch {
      setError(resolver ? "That code didn't work. Try the code your app shows now." : "Email or password is incorrect.");
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="stack">
      <ol className="progress" aria-label="Sign-in steps">
        <li className={resolver ? "done" : "current"}>Email and password</li>
        <li className={resolver ? "current" : ""}>Authenticator code</li>
      </ol>
      {!resolver ? (
        <>
          <label>
            Email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" required />
          </label>
          <label>
            Password
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
          </label>
        </>
      ) : (
        <label>
          Authenticator code
          <input
            inputMode="numeric"
            autoComplete="one-time-code"
            className="code-input"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            required
            autoFocus
          />
          <span className="hint">The 6-digit code in your authenticator app.</span>
        </label>
      )}
      {error && <p className="error" role="alert">{error}</p>}
      <button className="primary big" disabled={busy}>{busy ? "Checking…" : resolver ? "Verify and sign in" : "Next"}</button>
    </form>
  );
}
