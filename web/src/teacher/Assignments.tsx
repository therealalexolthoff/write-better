// A teacher's assignments: the list (with how far along everyone is) and one
// assignment's view (every student's stage, and adding students who joined
// the class later). Built by api/app/assignments.py.
import { useEffect, useState } from "react";
import { api } from "../api";
import type { AssignmentDetail, AssignmentSummary, ClassInfo, Progress } from "../types";
import { stateLabel } from "./ExerciseScreen";

const GROUPS: { key: keyof Progress; label: string; yours?: boolean }[] = [
  { key: "needs_you", label: "need you", yours: true },
  { key: "not_started", label: "not started" },
  { key: "writing", label: "writing" },
  { key: "with_student", label: "correcting" },
  { key: "done", label: "done" },
];
// Stages where the next step is the teacher's (as in the overview).
const TEACHER_TURN = ["transcript_review", "scrub_review", "draft_ready", "ready_to_release", "revision_submitted"];

const day = (iso: string) => new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });

export function ProgressChips({ progress }: { progress: Progress }) {
  const shown = GROUPS.filter((g) => progress[g.key] > 0);
  if (shown.length === 0) return <span className="muted">No students</span>;
  return (
    <span className="row chips">
      {shown.map((g) => (
        <span key={g.key} className={g.yours ? "stage yours" : "stage"}>
          {progress[g.key]} {g.key === "needs_you" && progress[g.key] === 1 ? "needs you" : g.label}
        </span>
      ))}
    </span>
  );
}

export function AssignmentList({
  classId,
  classes,
  onOpen,
}: {
  classId: string;
  classes: ClassInfo[];
  onOpen: (id: string) => void;
}) {
  const [list, setList] = useState<AssignmentSummary[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const query = classId ? `?class_id=${encodeURIComponent(classId)}` : "";
    api<AssignmentSummary[]>(`/assignments${query}`).then(setList, (err) => setError(err.message));
  }, [classId]);

  if (error) return <p className="error">{error}</p>;
  if (!list) return <p className="loading">Loading…</p>;
  if (list.length === 0) {
    return (
      <div className="empty">
        <h2>No assignments yet</h2>
        <p className="muted">Use “Assign writing” to set your first one.</p>
      </div>
    );
  }
  const className = (id: string) => classes.find((c) => c.class_id === id)?.name ?? "";
  return (
    <div className="table-scroll">
      <table className="middle">
        <thead>
          <tr><th>Assignment</th>{!classId && <th>Class</th>}<th>Set</th><th>Students</th><th>Progress</th></tr>
        </thead>
        <tbody>
          {list.map((a) => (
            <tr key={a.assignment_id} className="clickable" onClick={() => onOpen(a.assignment_id)}>
              <td><button className="link" onClick={(e) => { e.stopPropagation(); onOpen(a.assignment_id); }}>{a.title}</button></td>
              {!classId && <td>{className(a.class_id)}</td>}
              <td>{day(a.created_at)}</td>
              <td>{a.students}</td>
              <td><ProgressChips progress={a.progress} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function AssignmentScreen({
  assignmentId,
  className,
  onBack,
  onOpenExercise,
}: {
  assignmentId: string;
  className: (id: string) => string;
  onBack: () => void;
  onOpenExercise: (id: string) => void;
}) {
  const [detail, setDetail] = useState<AssignmentDetail | null>(null);
  const [error, setError] = useState("");
  const [adding, setAdding] = useState<Set<string>>(new Set());
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () => api<AssignmentDetail>(`/assignments/${assignmentId}`).then(setDetail, (err) => setError(err.message));
  useEffect(() => {
    load();
  }, [assignmentId]);

  async function add() {
    setBusy(true);
    setMessage("");
    try {
      await api(`/assignments/${assignmentId}/students`, "POST", { student_ids: [...adding] });
      setMessage(`Added ${adding.size} student${adding.size === 1 ? "" : "s"}.`);
      setAdding(new Set());
      await load();
    } catch (err) {
      setMessage((err as Error).message);
    }
    setBusy(false);
  }

  const toggle = (id: string) => {
    const next = new Set(adding);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setAdding(next);
  };

  return (
    <main className="page wide">
      <button className="link" onClick={onBack}>← All assignments</button>
      {error && <p className="error">{error}</p>}
      {detail && (
        <>
          <h1>{detail.title}</h1>
          <p className="muted">
            {className(detail.class_id)} · set {day(detail.created_at)}
          </p>
          <section className="panel">
            <h2>Prompt</h2>
            <p>{detail.prompt}</p>
            {(detail.min_words || detail.max_words) && (
              <p className="muted">
                Words: {[detail.min_words && `at least ${detail.min_words}`, detail.max_words && `at most ${detail.max_words}`].filter(Boolean).join(", ")}
              </p>
            )}
          </section>

          <div className="row spread">
            <h2>Students</h2>
            <ProgressChips progress={detail.progress} />
          </div>
          <div className="table-scroll">
            <table className="middle">
              <thead>
                <tr><th>Student</th><th>Stage</th></tr>
              </thead>
              <tbody>
                {detail.students.map((s) => (
                  <tr key={s.exercise_id} className="clickable" onClick={() => onOpenExercise(s.exercise_id)}>
                    <td><button className="link" onClick={(e) => { e.stopPropagation(); onOpenExercise(s.exercise_id); }}>{s.username}</button></td>
                    <td><span className={TEACHER_TURN.includes(s.state) ? "stage yours" : "stage"}>{stateLabel(s.state)}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {detail.not_assigned.length > 0 && (
            <section className="panel stack">
              <h2>Add students</h2>
              <p className="muted">These students are in the class but don't have this assignment, for example because they joined later.</p>
              <div className="choose-list">
                {detail.not_assigned.map((s) => (
                  <label key={s.student_id} className="check">
                    <input type="checkbox" checked={adding.has(s.student_id)} onChange={() => toggle(s.student_id)} />
                    {s.username}
                  </label>
                ))}
              </div>
              <div className="row">
                <button className="primary" disabled={busy || adding.size === 0} onClick={add}>
                  {busy ? "Adding…" : `Give it to ${adding.size || "the chosen"} student${adding.size === 1 ? "" : "s"}`}
                </button>
              </div>
            </section>
          )}
          {message && <p className="notice" aria-live="polite">{message}</p>}
        </>
      )}
    </main>
  );
}
