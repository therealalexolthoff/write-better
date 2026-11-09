// Where Identity Platform's email links land (its "action URL", set in
// infra/setup_gcp.sh): setting a password from a one-time link (new
// teachers created by the admin, the admin's own account, password
// resets) and confirming an email address (teacher sign-ups). Handled here,
// with the app's own sign-in key from the app's own address, rather than
// on Google's hosted page.
import { useEffect, useState, type FormEvent } from "react";
import { applyActionCode, confirmPasswordReset, verifyPasswordResetCode } from "firebase/auth";
import { authErrorMessage, currentAuth, initAuth } from "../firebase";
import { PublicLayout } from "../Layout";
import { Link, PATHS } from "../router";

const MIN_PASSWORD = 12;

type State =
  | { step: "checking" }
  | { step: "password"; email: string }
  | { step: "done"; message: string }
  | { step: "failed"; message: string };

export default function AccountAction() {
  const params = new URLSearchParams(window.location.search);
  const mode = params.get("mode");
  const code = params.get("oobCode") ?? "";
  const [state, setState] = useState<State>({ step: "checking" });

  useEffect(() => {
    const fail = (err: unknown) =>
      setState({ step: "failed", message: `This link didn't work. ${linkProblem(err)}` });
    initAuth()
      .then(async (auth) => {
        if (mode === "resetPassword") {
          setState({ step: "password", email: await verifyPasswordResetCode(auth, code) });
        } else if (mode === "verifyEmail") {
          await applyActionCode(auth, code);
          setState({ step: "done", message: "Your email address is confirmed. Go back to Write Better to continue." });
        } else {
          setState({ step: "failed", message: "This link isn't one Write Better uses." });
        }
      })
      .catch(fail);
  }, [mode, code]);

  return (
    <PublicLayout>
      <div className="auth-page">
        <section className="auth-card">
          {state.step === "checking" && <p className="loading" aria-live="polite">Checking your link…</p>}
          {state.step === "password" && <SetPassword email={state.email} code={code} onDone={(message) => setState({ step: "done", message })} />}
          {state.step === "done" && (
            <>
              <h1>All set</h1>
              <p className="notice" role="status">{state.message}</p>
              <Link to={PATHS.app} className="button primary big">Continue to Write Better</Link>
            </>
          )}
          {state.step === "failed" && (
            <>
              <h1>Link not valid</h1>
              <p className="error" role="alert">{state.message}</p>
              <Link to={PATHS.signIn} className="button">Go to sign in</Link>
            </>
          )}
        </section>
      </div>
    </PublicLayout>
  );
}

function SetPassword({ email, code, onDone }: { email: string; code: string; onDone: (message: string) => void }) {
  const [password, setPassword] = useState("");
  const [again, setAgain] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (password.length < MIN_PASSWORD) return setError(`Choose a password of at least ${MIN_PASSWORD} characters.`);
    if (password !== again) return setError("The two passwords don't match.");
    setBusy(true);
    setError("");
    try {
      await confirmPasswordReset(currentAuth(), code, password);
      onDone("Your password is set. Sign in with your email and new password.");
    } catch (err) {
      setError(linkProblem(err));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="stack">
      <h1>Set your password</h1>
      <p className="muted">For {email}</p>
      <input type="email" value={email} autoComplete="username" readOnly hidden />
      <label>
        New password
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" minLength={MIN_PASSWORD} required />
        <span className="hint">At least {MIN_PASSWORD} characters.</span>
      </label>
      <label>
        Type it again
        <input type="password" value={again} onChange={(e) => setAgain(e.target.value)} autoComplete="new-password" required />
      </label>
      {error && <p className="error" role="alert">{error}</p>}
      <button className="primary big" disabled={busy}>{busy ? "Saving…" : "Set password"}</button>
    </form>
  );
}

function linkProblem(err: unknown): string {
  const code = (err as { code?: string }).code ?? "";
  if (code === "auth/expired-action-code") return "It has expired. Ask for a new one.";
  if (code === "auth/invalid-action-code") return "It has already been used, or it's incomplete. Ask for a new one.";
  return authErrorMessage(err);
}
