// Set a piece of writing for a class: the teacher writes the prompt (the AI
// never does) and assigns it to the whole class or chosen students in it.
// Each student gets their own copy straight away. The API checks everything
// again (api/app/assignments.py).
import { useState, type FormEvent } from "react";
import { api } from "../api";
import type { ClassInfo, Student } from "../types";

type Who = "class" | "chosen";

export default function AssignWriting({
  classes,
  classId,
  students,
  onDone,
}: {
  classes: ClassInfo[]; // open classes only
  classId: string; // the class being shown, or "" for all
  students: Student[]; // the teacher's active students
  onDone: (message: string, assignmentId: string) => void;
}) {
  const [target, setTarget] = useState(classes.some((c) => c.class_id === classId) ? classId : classes[0]?.class_id ?? "");
  const [title, setTitle] = useState("");
  const [prompt, setPrompt] = useState("");
  const [minWords, setMinWords] = useState("");
  const [maxWords, setMaxWords] = useState("");
  const [who, setWho] = useState<Who>("class");
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const inClass = students.filter((s) => s.class_id === target);
  const className = classes.find((c) => c.class_id === target)?.name ?? "";
  const count = who === "class" ? inClass.length : chosen.size;
  const plural = (n: number) => `${n} student${n === 1 ? "" : "s"}`;

  const toggle = (id: string) => {
    const next = new Set(chosen);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setChosen(next);
  };

  function review(e: FormEvent) {
    e.preventDefault();
    const problem = count === 0 ? (who === "class" ? "This class has no active students yet." : "Pick at least one student.") : "";
    setError(problem);
    if (!problem) setConfirming(true);
  }

  async function assign() {
    setBusy(true);
    setError("");
    try {
      const draft = {
        kind: "writing",
        title,
        prompt,
        min_words: minWords ? Number(minWords) : null,
        max_words: maxWords ? Number(maxWords) : null,
      };
      // Keep the order of the class list.
      const student_ids = who === "class" ? undefined : inClass.filter((s) => chosen.has(s.student_id)).map((s) => s.student_id);
      const { assignment_id } = await api<{ assignment_id: string }>("/assignments", "POST", { class_id: target, draft, student_ids });
      onDone(`“${title}” was assigned to ${plural(count)} in ${className}.`, assignment_id);
    } catch (err) {
      setError((err as Error).message);
      setConfirming(false);
      setBusy(false);
    }
  }

  if (classes.length === 0) {
    return <p className="notice">Create a class first, or reopen an archived one, to assign writing.</p>;
  }

  return (
    <form onSubmit={review} className="panel stack">
      <h2>Assign writing</h2>
      <p className="muted">
        Write the prompt yourself. Each student gets their own copy straight away. It can't be edited after assigning.
      </p>
      <label>
        Class
        <select
          className="block-select"
          value={target}
          onChange={(e) => { setTarget(e.target.value); setChosen(new Set()); }}
          disabled={confirming}
        >
          {classes.map((c) => <option key={c.class_id} value={c.class_id}>{c.name}</option>)}
        </select>
      </label>
      <label>
        Title
        <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} required disabled={confirming} />
      </label>
      <label>
        Prompt
        <textarea rows={4} value={prompt} onChange={(e) => setPrompt(e.target.value)} required disabled={confirming} />
        <span className="hint">What the students see, for example "Write an email to a hotel asking about a room."</span>
      </label>
      <div className="row">
        <label>
          Min words (optional)
          <input type="number" min={1} className="narrow-input" value={minWords} onChange={(e) => setMinWords(e.target.value)} disabled={confirming} />
        </label>
        <label>
          Max words (optional)
          <input type="number" min={1} className="narrow-input" value={maxWords} onChange={(e) => setMaxWords(e.target.value)} disabled={confirming} />
        </label>
      </div>

      <fieldset disabled={confirming}>
        <legend>Who gets it</legend>
        <label className="check">
          <input type="radio" name="who" checked={who === "class"} onChange={() => setWho("class")} />
          The whole class ({plural(inClass.length)})
        </label>
        <label className="check">
          <input type="radio" name="who" checked={who === "chosen"} onChange={() => setWho("chosen")} />
          Choose students
        </label>
        {who === "chosen" && (
          <div className="choose-list">
            {inClass.length === 0 && <p className="muted">No active students in this class yet.</p>}
            {inClass.map((s) => (
              <label key={s.student_id} className="check">
                <input type="checkbox" checked={chosen.has(s.student_id)} onChange={() => toggle(s.student_id)} />
                {s.username}
              </label>
            ))}
          </div>
        )}
      </fieldset>

      {confirming ? (
        <div className="confirm">
          <p>
            <strong>Assign “{title}” to {plural(count)} in {className} now?</strong> They'll see it straight away, and it
            can't be changed after this.
          </p>
          <div className="row">
            <button type="button" className="primary" onClick={assign} disabled={busy}>
              {busy ? "Assigning…" : "Yes, assign"}
            </button>
            <button type="button" onClick={() => setConfirming(false)} disabled={busy}>Not yet</button>
          </div>
        </div>
      ) : (
        <button className="primary">Assign…</button>
      )}
      {error && <p className="error pre">{error}</p>}
    </form>
  );
}
