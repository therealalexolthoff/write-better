// The admin's screens: approve or reject teacher sign-ups, and manage
// teacher accounts. Every rule is enforced by the API (api/app/admin.py);
// this only collects input. The admin never sees student work.
import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api";

type Signup = { uid: string; name: string; email: string; email_verified: boolean; created_at: string };
type Teacher = { uid: string; name: string; email: string; active: boolean; student_count: number };
type Tab = "signups" | "teachers";

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
      </div>
      {tab === "signups" ? <Signups /> : <Teachers />}
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
