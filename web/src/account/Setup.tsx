// First sign-in for a teacher or the admin: verify the email, then set up
// an authenticator app. The API refuses their sign-ins until both are done
// (api/app/auth.py), so this is all they see until then. Afterwards they
// sign in again, this time with the code.
import { useState, type FormEvent } from "react";
import {
  authErrorMessage,
  finishAuthenticatorSetup,
  logOut,
  refreshAccount,
  resendVerificationEmail,
  startAuthenticatorSetup,
  type AuthenticatorSetup,
} from "../firebase";
import QrCode from "../QrCode";
import { PATHS, navigate } from "../router";

export default function Setup({ email, emailVerified }: { email: string | null; emailVerified: boolean }) {
  return (
    <main className="page narrow">
      <h1>Set up your account</h1>
      <p className="lead">Two quick steps keep your students' work safe. You only do this once.</p>
      <ol className="progress" aria-label="Setup steps">
        <li className={emailVerified ? "done" : "current"}>Verify your email</li>
        <li className={emailVerified ? "current" : ""}>Authenticator app</li>
      </ol>
      {emailVerified ? <AuthenticatorStep /> : <VerifyEmailStep email={email} />}
    </main>
  );
}

function VerifyEmailStep({ email }: { email: string | null }) {
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function act(action: () => Promise<void>, done: string) {
    setBusy(true);
    setMessage("");
    try {
      await action();
      setMessage(done);
    } catch (err) {
      setMessage(authErrorMessage(err));
    }
    setBusy(false);
  }

  return (
    <section className="panel stack">
      <h2>Verify your email</h2>
      <p>
        Open the link we sent to <strong>{email}</strong>, then come back here. Can't find it? Check your spam folder, or
        send it again.
      </p>
      <div className="row">
        <button className="primary" disabled={busy} onClick={() => act(refreshAccount, "Not verified yet. Open the link in the email first.")}>
          I've verified it
        </button>
        <button disabled={busy} onClick={() => act(resendVerificationEmail, "Sent. Check your inbox.")}>Send the link again</button>
      </div>
      {message && <p className="notice" aria-live="polite">{message}</p>}
    </section>
  );
}

// Exported for the screen preview, which shows it with a sample key.
export function AuthenticatorStep({ initial = null }: { initial?: Pick<AuthenticatorSetup, "key" | "url"> | null }) {
  const [setup, setSetup] = useState<AuthenticatorSetup | Pick<AuthenticatorSetup, "key" | "url"> | null>(initial);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function start() {
    setBusy(true);
    setError("");
    try {
      setSetup(await startAuthenticatorSetup());
    } catch (err) {
      setError(authErrorMessage(err));
    }
    setBusy(false);
  }

  async function finish(e: FormEvent) {
    e.preventDefault();
    if (!setup || !("secret" in setup)) return;
    setBusy(true);
    setError("");
    try {
      await finishAuthenticatorSetup(setup, code);
      await logOut();
      navigate(`${PATHS.signIn}?ready=1`, { replace: true });
    } catch (err) {
      setError(authErrorMessage(err));
      setBusy(false);
    }
  }

  return (
    <section className="panel stack">
      <h2>Set up an authenticator app</h2>
      <p>
        Each time you sign in, you'll enter a 6-digit code from an app on your phone, such as Google Authenticator,
        Microsoft Authenticator or Authy. Install one first if you need to.
      </p>
      {!setup ? (
        <button className="primary" disabled={busy} onClick={start}>{busy ? "Preparing…" : "Start"}</button>
      ) : (
        <form onSubmit={finish} className="stack">
          <ol className="numbered">
            <li>
              In the app, add an account and scan this code:
              <QrCode text={setup.url} label="QR code to add Write Better to your authenticator app" />
              <details className="key-fallback">
                <summary>Can't scan it?</summary>
                <p>
                  Choose <strong>Enter a setup key</strong> (sometimes "Enter key manually") in the app, and type this key:
                </p>
                <code className="setup-key">{setup.key.replace(/(.{4})/g, "$1 ").trim()}</code>
                <span className="hint">On this phone? <a href={setup.url}>Open it in your authenticator app</a> instead.</span>
              </details>
            </li>
            <li>
              <label>
                Enter the 6-digit code the app shows
                <input
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  className="code-input"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  required
                />
              </label>
            </li>
          </ol>
          <button className="primary big" disabled={busy}>{busy ? "Checking…" : "Finish setup"}</button>
        </form>
      )}
      {error && <p className="error" role="alert">{error}</p>}
    </section>
  );
}
