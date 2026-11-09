// Student accounts (FR-1, FR-4): add, reset password, deactivate, and
// delete (with type-the-name confirmation).
import { useState, type FormEvent } from "react";
import { api } from "../api";
import type { Student } from "../types";

export default function StudentsPanel({ students, onChange }: { students: Student[]; onChange: () => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [deleting, setDeleting] = useState<Student | null>(null);
  const [typed, setTyped] = useState("");

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

  function add(e: FormEvent) {
    e.preventDefault();
    run(async () => {
      await api("/students", "POST", { username, password });
      setUsername("");
      setPassword("");
    }, `Added ${username}.`);
  }

  function resetPassword(s: Student) {
    const newPassword = window.prompt(`New password for ${s.username} (at least 8 characters):`);
    if (newPassword) run(() => api(`/students/${s.student_id}/reset-password`, "POST", { password: newPassword }), `Password reset for ${s.username}.`);
  }

  function deactivate(s: Student) {
    if (window.confirm(`Deactivate ${s.username}? They won't be able to sign in.`)) {
      run(() => api(`/students/${s.student_id}/deactivate`, "POST"), `${s.username} deactivated.`);
    }
  }

  function remove(s: Student) {
    run(async () => {
      await api(`/students/${s.student_id}`, "DELETE", { confirm_username: typed });
      setDeleting(null);
      setTyped("");
    }, `${s.username} and all their data were deleted.`);
  }

  return (
    <section className="panel">
      <h2>Students</h2>
      {students.length === 0 ? (
        <p className="muted">No students yet. Add your first one below.</p>
      ) : (
        <table className="middle">
          <thead>
            <tr><th>Username</th><th>Status</th><th><span className="visually-hidden">Actions</span></th></tr>
          </thead>
          <tbody>
            {students.map((s) => (
              <tr key={s.student_id}>
                <td><strong>{s.username}</strong></td>
                <td><span className={`badge ${s.active ? "released" : ""}`}>{s.active ? "Active" : "Deactivated"}</span></td>
                <td className="actions">
                  {s.active && <button className="small" onClick={() => resetPassword(s)}>Reset password</button>}
                  {s.active && <button className="small" onClick={() => deactivate(s)}>Deactivate</button>}
                  <button className="small danger" onClick={() => { setDeleting(s); setTyped(""); setMessage(""); }}>Delete…</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {deleting && (
        <div className="confirm stack">
          <p>
            <strong>Delete {deleting.username} for good?</strong> This deletes their account, all their writing,
            photos and your notes. It can't be undone. Copies in the daily backups expire within 7
            days.
          </p>
          <label>
            Type {deleting.username} to confirm
            <input value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" />
          </label>
          <div className="row">
            <button className="danger" onClick={() => remove(deleting)} disabled={typed !== deleting.username}>Delete permanently</button>
            <button onClick={() => setDeleting(null)}>Cancel</button>
          </div>
        </div>
      )}
      <form onSubmit={add} className="add-form">
        <h3>Add a student</h3>
        <div className="row top">
          <label className="grow">
            Username
            <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="off" autoCapitalize="none" required />
            <span className="hint">First name and initial, for example maria.k. No surnames.</span>
          </label>
          <label className="grow">
            Password
            <input value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" minLength={8} required />
            <span className="hint">At least 8 characters. Give it to the student in class.</span>
          </label>
        </div>
        <button className="primary">Add student</button>
      </form>
      {message && <p className="notice">{message}</p>}
    </section>
  );
}
