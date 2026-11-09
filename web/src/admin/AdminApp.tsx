// The admin's screens: approve or reject teacher sign-ups, and manage
// teacher accounts. Every rule is enforced by the API (api/app/admin.py);
// this only collects input. The admin never sees student work.
import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api";
import type { Spending } from "../types";

type Signup = { uid: string; name: string; email: string; email_verified: boolean; created_at: string };
type Teacher = { uid: string; name: string; email: string; active: boolean; student_count: number };
type Tab = "signups" | "teachers" | "spending";

export default function AdminApp({ initialTab = "signups" }: { initialTab?: Tab }) {
  const [tab, setTab] = useState<Tab>(initialTab);
  return (
    <main className="page wide">
      <h1>Admin</h1>
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === "signups"} className={tab === "signups" ? "active" : ""} onClick={() => setTab("signups")}>
          Sign-ups
        </button>
        <button role="tab" aria-selected={tab === "teachers"} className={tab === "teachers" ? "active" : ""} onClick={() => setTab("teachers")}>
          Teachers
        </button>
        <button role="tab" aria-selected={tab === "spending"} className={tab === "spending" ? "active" : ""} onClick={() => setTab("spending")}>
          Spending
        </button>
      </div>
      {tab === "signups" ? <Signups /> : tab === "teachers" ? <Teachers /> : <SpendingTab />}
    </main>
  );
}

const day = (iso: string) => new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });

function useAction(reload: () => void) {
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  async function run(action: () => Promise<unknown>, done: string) {
    setBusy(true);
    setMessage("");
    try {
      await action();
      setMessage(done);
      reload();
    } catch (err) {
      setMessage((err as Error).message);
    }
    setBusy(false);
  }
  return { message, busy, run, setMessage };
}

// ---- sign-ups ----

function Signups() {
  const [list, setList] = useState<Signup[] | null>(null);
  const [error, setError] = useState("");
  const load = () => api<Signup[]>("/admin/signups").then(setList, (err) => setError(err.message));
  useEffect(() => {
    load();
  }, []);
  const { message, busy, run } = useAction(load);

  function reject(s: Signup) {
    if (window.confirm(`Reject ${s.name} (${s.email})? Their login is deleted.`)) {
      run(() => api(`/admin/signups/${s.uid}/reject`, "POST"), `${s.name} was rejected.`);
    }
  }

  if (error) return <p className="error">{error}</p>;
  if (!list) return <p className="loading">Loading…</p>;
  return (
    <>
      <p className="muted">
        New teachers wait here until you approve them. Requests not handled within 30 days are deleted.
      </p>
      {list.length === 0 ? (
        <div className="empty">
          <h2>No sign-ups waiting</h2>
          <p className="muted">You'll get an email when a teacher signs up.</p>
        </div>
      ) : (
        <div className="table-scroll"><table className="middle">
          <thead>
            <tr><th>Name</th><th>Email</th><th>Email verified</th><th>Signed up</th><th><span className="visually-hidden">Actions</span></th></tr>
          </thead>
          <tbody>
            {list.map((s) => (
              <tr key={s.uid}>
                <td><strong>{s.name}</strong></td>
                <td>{s.email}</td>
                <td><span className={`badge ${s.email_verified ? "released" : ""}`}>{s.email_verified ? "Yes" : "Not yet"}</span></td>
                <td>{day(s.created_at)}</td>
                <td className="actions">
                  <button className="small primary" disabled={busy} onClick={() => run(() => api(`/admin/signups/${s.uid}/approve`, "POST"), `${s.name} is now a teacher.`)}>
                    Approve
                  </button>
                  <button className="small danger" disabled={busy} onClick={() => reject(s)}>Reject…</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table></div>
      )}
      {message && <p className="notice" aria-live="polite">{message}</p>}
    </>
  );
}

// ---- teachers ----

function Teachers() {
  const [list, setList] = useState<Teacher[] | null>(null);
  const [error, setError] = useState("");
  const [link, setLink] = useState<{ label: string; url: string } | null>(null);
  const [transferring, setTransferring] = useState<Teacher | null>(null);
  const load = () => api<Teacher[]>("/admin/teachers").then(setList, (err) => setError(err.message));
  useEffect(() => {
    load();
  }, []);
  const { message, busy, run } = useAction(load);

  function getLink(t: Teacher) {
    run(async () => {
      const { link: url } = await api<{ link: string }>(`/admin/teachers/${t.uid}/password-link`, "POST");
      setLink({ label: `Password link for ${t.name}`, url });
    }, "");
  }

  function resetAuthenticator(t: Teacher) {
    if (window.confirm(`Reset ${t.name}'s authenticator app? They'll set up a new one the next time they sign in.`)) {
      run(() => api(`/admin/teachers/${t.uid}/reset-authenticator`, "POST"), `${t.name} will set up a new authenticator app at their next sign-in.`);
    }
  }

  function toggle(t: Teacher) {
    if (t.active && !window.confirm(`Deactivate ${t.name}? They can't sign in until you reactivate them. Their students and work are kept.`)) return;
    run(() => api(`/admin/teachers/${t.uid}/${t.active ? "deactivate" : "reactivate"}`, "POST"), `${t.name} ${t.active ? "deactivated" : "reactivated"}.`);
  }

  if (error) return <p className="error">{error}</p>;
  if (!list) return <p className="loading">Loading…</p>;
  return (
    <>
      <NewTeacher onCreated={(name, url) => { setLink({ label: `Setup link for ${name}`, url }); load(); }} />
      {link && <LinkBox label={link.label} url={link.url} onClose={() => setLink(null)} />}

      {list.length === 0 ? (
        <div className="empty"><h2>No teachers yet</h2><p className="muted">Approve a sign-up or add a teacher above.</p></div>
      ) : (
        <div className="table-scroll"><table className="middle">
          <thead>
            <tr><th>Name</th><th>Email</th><th>Status</th><th>Students</th><th><span className="visually-hidden">Actions</span></th></tr>
          </thead>
          <tbody>
            {list.map((t) => (
              <tr key={t.uid}>
                <td><strong>{t.name}</strong></td>
                <td>{t.email}</td>
                <td><span className={`badge ${t.active ? "released" : ""}`}>{t.active ? "Active" : "Deactivated"}</span></td>
                <td>{t.student_count}</td>
                <td className="actions">
                  <button className="small" disabled={busy} onClick={() => getLink(t)}>Password link</button>
                  <button className="small" disabled={busy} onClick={() => resetAuthenticator(t)}>Reset authenticator…</button>
                  <button className="small" disabled={busy || t.student_count === 0} onClick={() => setTransferring(t)}>Transfer students…</button>
                  <button className={`small${t.active ? " danger" : ""}`} disabled={busy} onClick={() => toggle(t)}>
                    {t.active ? "Deactivate…" : "Reactivate"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table></div>
      )}
      {transferring && (
        <Transfer
          from={transferring}
          to={list.filter((t) => t.active && t.uid !== transferring.uid)}
          busy={busy}
          onCancel={() => setTransferring(null)}
          onTransfer={(to) =>
            run(async () => {
              await api(`/admin/teachers/${transferring.uid}/transfer`, "POST", { to_teacher_id: to.uid });
              setTransferring(null);
            }, `${transferring.name}'s students and their work now belong to ${to.name}.`)
          }
        />
      )}
      {message && <p className="notice" aria-live="polite">{message}</p>}
    </>
  );
}

function NewTeacher({ onCreated }: { onCreated: (name: string, url: string) => void }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const { setup_link } = await api<{ setup_link: string }>("/admin/teachers", "POST", { name, email });
      onCreated(name, setup_link);
      setName("");
      setEmail("");
    } catch (err) {
      setError((err as Error).message);
    }
    setBusy(false);
  }

  return (
    <form onSubmit={submit} className="panel">
      <h2>Add a teacher</h2>
      <p className="muted">For teachers who haven't signed up themselves. You'll get a link to send them, to set their password.</p>
      <div className="row top">
        <label className="grow">
          Name
          <input value={name} onChange={(e) => setName(e.target.value)} maxLength={100} required />
        </label>
        <label className="grow">
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      <button className="primary" disabled={busy}>{busy ? "Adding…" : "Add teacher"}</button>
    </form>
  );
}

// A one-time link for the admin to send: there is no email service.
function LinkBox({ label, url, onClose }: { label: string; url: string; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  return (
    <section className="panel link-box" aria-live="polite">
      <h2>{label}</h2>
      <p>Send this to the teacher yourself, for example by email. It works once, and only for a limited time.</p>
      <div className="row">
        <input readOnly value={url} className="grow" onFocus={(e) => e.target.select()} aria-label={label} />
        <button className="primary" onClick={() => navigator.clipboard.writeText(url).then(() => setCopied(true))}>
          {copied ? "Copied" : "Copy"}
        </button>
        <button onClick={onClose}>Done</button>
      </div>
    </section>
  );
}

function Transfer({
  from,
  to,
  busy,
  onCancel,
  onTransfer,
}: {
  from: Teacher;
  to: Teacher[];
  busy: boolean;
  onCancel: () => void;
  onTransfer: (to: Teacher) => void;
}) {
  const [target, setTarget] = useState(to[0]?.uid ?? "");
  const chosen = to.find((t) => t.uid === target);
  return (
    <section className="confirm stack">
      <p>
        <strong>Transfer {from.name}'s {from.student_count} student{from.student_count === 1 ? "" : "s"}?</strong> Their
        accounts and all their work move to the teacher you choose. {from.name} won't see them any more.
      </p>
      {to.length === 0 ? (
        <p>There's no other active teacher to transfer to.</p>
      ) : (
        <label>
          Transfer to{" "}
          <select value={target} onChange={(e) => setTarget(e.target.value)}>
            {to.map((t) => <option key={t.uid} value={t.uid}>{t.name}</option>)}
          </select>
        </label>
      )}
      <div className="row">
        <button className="primary" disabled={busy || !chosen} onClick={() => chosen && onTransfer(chosen)}>Transfer</button>
        <button onClick={onCancel}>Cancel</button>
      </div>
    </section>
  );
}

// ---- spending ----

const dollars = (n: number) => `$${n.toFixed(2)}`;
const monthName = (key: string) =>
  new Date(`${key}-01T00:00:00Z`).toLocaleDateString(undefined, { month: "long", year: "numeric", timeZone: "UTC" });
const OPERATIONS: Record<string, string> = { evaluate_writing: "Writing feedback", transcribe: "Handwriting transcription" };

function SpendingTab() {
  const [data, setData] = useState<Spending | null>(null);
  const [error, setError] = useState("");
  const [cap, setCap] = useState("");
  const load = () =>
    api<Spending>("/admin/spending").then((d) => {
      setData(d);
      setCap(d.cap_usd.toFixed(2));
    }, (err) => setError(err.message));
  useEffect(() => {
    load();
  }, []);
  const { message, busy, run } = useAction(load);

  if (error) return <p className="error">{error}</p>;
  if (!data) return <p className="loading">Loading…</p>;

  const share = data.cap_usd > 0 ? Math.min(1, data.total_usd / data.cap_usd) : 1;
  const level = data.paused ? "critical" : share >= 0.75 ? "warning" : "ok";
  const status = data.paused
    ? "Paused: the cap is reached, so AI feedback is off until next month or a higher cap."
    : share >= 0.75
      ? "Over 75% of the cap. AI feedback pauses when the cap is reached."
      : "Within the cap.";

  function saveCap(e: FormEvent) {
    e.preventDefault();
    run(() => api("/admin/spending/cap", "PUT", { monthly_cap_usd: Number(cap) }), `The monthly cap is now ${dollars(Number(cap))}.`);
  }

  return (
    <>
      <section className="panel">
        <h2>{monthName(data.month)}</h2>
        <p className="stat">
          <span className="stat-value">{dollars(data.total_usd)}</span>
          <span className="stat-label">of a {dollars(data.cap_usd)} AI cap · {data.calls} AI call{data.calls === 1 ? "" : "s"}</span>
        </p>
        <div
          className={`meter ${level}`}
          role="meter"
          aria-valuemin={0}
          aria-valuemax={data.cap_usd}
          aria-valuenow={data.total_usd}
          aria-label={`AI spend this month: ${dollars(data.total_usd)} of ${dollars(data.cap_usd)}`}
        >
          <span className="meter-fill" style={{ width: `${share * 100}%` }} />
        </div>
        <p className={`status-line ${level}`}>
          <span className="status-icon" aria-hidden="true">{level === "ok" ? "✓" : "!"}</span>
          {status}
        </p>
        {data.failed_calls > 0 && (
          <p className="muted">
            {data.failed_calls} call{data.failed_calls === 1 ? "" : "s"} failed this month. Teachers can retry them; nothing was lost.
          </p>
        )}
      </section>

      <form onSubmit={saveCap} className="panel">
        <h2>Monthly AI cap</h2>
        <p className="muted">
          AI feedback and transcription pause when this month's spend reaches the cap. Everything must stay under $20 a
          month including hosting, so the cap can't go above {dollars(data.max_cap_usd)}. Set 0 to pause AI entirely.
        </p>
        <div className="row">
          <label>
            Cap (US dollars)
            <input type="number" min={0} max={data.max_cap_usd} step="0.5" className="narrow-input wide-number" value={cap} onChange={(e) => setCap(e.target.value)} required />
          </label>
        </div>
        <button className="primary" disabled={busy || Number(cap) === data.cap_usd}>Save cap</button>
      </form>
      {message && <p className="notice" aria-live="polite">{message}</p>}

      <div className="split-tables">
        <section>
          <h2>By task</h2>
          {data.by_operation.length === 0 ? (
            <p className="muted">No AI calls yet this month.</p>
          ) : (
            <table className="middle">
              <thead><tr><th>Task</th><th>Calls</th><th>Cost</th></tr></thead>
              <tbody>
                {data.by_operation.map((row) => (
                  <tr key={row.operation}><td>{OPERATIONS[row.operation] ?? row.operation}</td><td>{row.calls}</td><td>{dollars(row.cost_usd)}</td></tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
        <section>
          <h2>By teacher</h2>
          {data.by_teacher.length === 0 ? (
            <p className="muted">No AI calls yet this month.</p>
          ) : (
            <table className="middle">
              <thead><tr><th>Teacher</th><th>Calls</th><th>Cost</th></tr></thead>
              <tbody>
                {data.by_teacher.map((row) => (
                  <tr key={row.uid}><td>{row.name}</td><td>{row.calls}</td><td>{dollars(row.cost_usd)}</td></tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>

      {data.months.length > 0 && (
        <section>
          <h2>Recent months</h2>
          <table className="middle">
            <thead><tr><th>Month</th><th>AI calls</th><th>AI spend</th></tr></thead>
            <tbody>
              {data.months.map((m) => (
                <tr key={m.month}><td>{monthName(m.month)}</td><td>{m.calls}</td><td>{dollars(m.total_usd)}</td></tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </>
  );
}
