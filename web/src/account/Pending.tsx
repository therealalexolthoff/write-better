// A signed-in account with no role yet: a teacher sign-up waiting for the
// admin. Shows where they are (email verified? approved?) and lets them
// check again. If the sign-up request never reached the API, they can send
// it from here.
import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../api";
import { authErrorMessage, refreshAccount, resendVerificationEmail } from "../firebase";

type Status = { status: string; email_verified: boolean };

export default function Pending({ email }: { email: string | null }) {
  const [status, setStatus] = useState<Status | null | undefined>(undefined); // null: no request
  const [message, setMessage] = useState(() => sessionStorage.getItem("signup-error") ?? "");
  const [busy, setBusy] = useState(false);

  const load = () =>
    api<Status>("/signup/me").then(setStatus, (err) => (err instanceof ApiError && err.status === 404 ? setStatus(null) : setMessage(err.message)));
  useEffect(() => {
    sessionStorage.removeItem("signup-error");
    load();
  }, []);

  async function act(action: () => Promise<unknown>, done = "") {
    setBusy(true);
    setMessage("");
    try {
      await action();
      setMessage(done);
    } catch (err) {
      setMessage(err instanceof ApiError ? err.message : authErrorMessage(err));
    }
    setBusy(false);
  }

  if (status === undefined) return <p className="loading" aria-live="polite">Loading…</p>;
  if (status === null) return <FinishSignUp onDone={load} message={message} />;

  const verified = status.email_verified;
  return (
    <main className="page narrow">
      <h1>Waiting for approval</h1>
      <p className="lead">Thanks for signing up. The Write Better administrator approves each new teacher account.</p>
      <ol className="checklist">
        <li className="done">
          <strong>Account created</strong>
          <span>{email}</span>
        </li>
        <li className={verified ? "done" : "current"}>
          <strong>Verify your email</strong>
          {verified ? (
            <span>Done.</span>
          ) : (
            <>
              <span>We sent a link to {email}. Open it, then come back here.</span>
              <div className="row">
                <button className="small" disabled={busy} onClick={() => act(resendVerificationEmail, "Sent. Check your inbox and spam folder.")}>
                  Send the link again
                </button>
              </div>
            </>
          )}
        </li>
        <li className="current">
          <strong>Approval</strong>
          <span>There's no email when you're approved: check back here, or ask the administrator.</span>
        </li>
      </ol>
      <div className="row">
        <button className="primary" disabled={busy} onClick={() => act(async () => { await refreshAccount(); await load(); }, "Checked. Still waiting for approval.")}>
          Check again
        </button>
      </div>
      {message && <p className="notice" aria-live="polite">{message}</p>}
    </main>
  );
}

// The login exists but the request didn't arrive (for example the daily
// limit, or a lost connection): send it again.
function FinishSignUp({ onDone, message }: { onDone: () => void; message: string }) {
  const [name, setName] = useState("");
  const [error, setError] = useState(message);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/signup", "POST", { name });
      onDone();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <main className="page narrow">
      <h1>Finish signing up</h1>
      <p>Your account was created, but your request to become a teacher didn't reach us. Send it again:</p>
      <form onSubmit={submit} className="panel stack">
        <label>
          Your name
          <input value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" maxLength={100} required />
        </label>
        {error && <p className="error" role="alert">{error}</p>}
        <button className="primary" disabled={busy}>{busy ? "Sending…" : "Send my request"}</button>
      </form>
      <p className="muted">If you're a student, your teacher creates your account: ask them for your username.</p>
    </main>
  );
}
