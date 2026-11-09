// The teacher's classes: create, rename, archive and reopen. Archiving keeps
// a class's students and their work; it just takes no new students. Every
// rule is enforced by the API (api/app/classes.py).
import { useState, type FormEvent } from "react";
import { api } from "../api";
import type { ClassInfo } from "../types";

export default function ClassesPanel({
  classes,
  onChange,
  firstRun = false,
}: {
  classes: ClassInfo[];
  onChange: () => void;
  firstRun?: boolean;
}) {
  const [name, setName] = useState("");
  const [renaming, setRenaming] = useState<string | null>(null);
  const [newName, setNewName] = useState("");
  const [message, setMessage] = useState("");

  async function run(action: () => Promise<unknown>, done: string) {
    setMessage("");
    try {
      await action();
      setMessage(done);
      onChange();
    } catch (err) {
      setMessage((err as Error).message);
    }
  }

  function create(e: FormEvent) {
    e.preventDefault();
    const created = name.trim();
    run(async () => {
      await api("/classes", "POST", { name: created });
      setName("");
    }, `Created ${created}.`);
  }

  function rename(e: FormEvent, c: ClassInfo) {
    e.preventDefault();
    run(async () => {
      await api(`/classes/${c.class_id}`, "PUT", { name: newName });
      setRenaming(null);
    }, `Renamed to ${newName.trim()}.`);
  }

  return (
    <section className="panel">
      {!firstRun && <h2>Classes</h2>}
      {classes.length > 0 && (
        <div className="table-scroll">
          <table className="middle">
            <thead>
              <tr><th>Class</th><th>Students</th><th>Status</th><th><span className="visually-hidden">Actions</span></th></tr>
            </thead>
            <tbody>
              {classes.map((c) => (
                <tr key={c.class_id}>
                  <td>
                    {renaming === c.class_id ? (
                      <form className="row" onSubmit={(e) => rename(e, c)}>
                        <input value={newName} onChange={(e) => setNewName(e.target.value)} maxLength={80} required aria-label="New class name" autoFocus />
                        <button className="small primary">Save</button>
                        <button type="button" className="small" onClick={() => setRenaming(null)}>Cancel</button>
                      </form>
                    ) : (
                      <strong>{c.name}</strong>
                    )}
                  </td>
                  <td>{c.student_count}</td>
                  <td><span className={`badge ${c.archived ? "" : "released"}`}>{c.archived ? "Archived" : "Open"}</span></td>
                  <td className="actions">
                    {renaming !== c.class_id && (
                      <button className="small" onClick={() => { setRenaming(c.class_id); setNewName(c.name); setMessage(""); }}>Rename</button>
                    )}
                    {c.archived ? (
                      <button className="small" onClick={() => run(() => api(`/classes/${c.class_id}/reopen`, "POST"), `${c.name} is open again.`)}>Reopen</button>
                    ) : (
                      <button className="small" onClick={() => run(() => api(`/classes/${c.class_id}/archive`, "POST"), `${c.name} archived. Its students and their work are kept.`)}>
                        Archive
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <form onSubmit={create} className={classes.length > 0 ? "add-form" : ""}>
        <h3>{firstRun ? "Create your first class" : "New class"}</h3>
        <div className="row top">
          <label className="grow">
            Class name
            <input value={name} onChange={(e) => setName(e.target.value)} maxLength={80} required />
            <span className="hint">For example "Tuesday evening" or "Advanced writing, autumn".</span>
          </label>
        </div>
        <button className="primary">Create class</button>
      </form>
      {message && <p className="notice" aria-live="polite">{message}</p>}
    </section>
  );
}
