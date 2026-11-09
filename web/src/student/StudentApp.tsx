import { useEffect, useState } from "react";
import { api } from "../api";
import type { ExerciseSummary } from "../types";
import DoExercise from "./DoExercise";

// Plain-English labels for the submission states (FR-35: no jargon).
export function stateLabel(state: string): string {
  if (state === "assigned") return "New";
  if (state === "in_progress") return "In progress";
  if (state === "released") return "Results ready";
  if (state === "revision_open") return "Results ready – you can make corrections";
  if (state === "revision_submitted") return "Corrections sent";
  if (state === "revision_reviewed") return "Corrections checked – see how you did";
  return "Submitted – waiting for your teacher";
}

export default function StudentApp() {
  const [exercises, setExercises] = useState<ExerciseSummary[] | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (open) return;
    api<ExerciseSummary[]>("/me/exercises")
      .then(setExercises)
      .catch(() => setError("Could not load your work. Check your connection and try again."));
  }, [open]);

  if (open) return <DoExercise exerciseId={open} onBack={() => setOpen(null)} />;

  return (
    <main className="page narrow">
      <h1>My work</h1>
      {error && <p className="error">{error}</p>}
      {exercises === null && !error && <p>Loading…</p>}
      {exercises?.length === 0 && <p>Nothing here yet. Your teacher will tell you when there's new work.</p>}
      <ul className="cards">
        {exercises?.map((ex) => (
          <li key={ex.exercise_id}>
            <button className="card" onClick={() => setOpen(ex.exercise_id)}>
              <strong>{ex.title}</strong>
              <span className={`badge ${ex.state}`}>{stateLabel(ex.state)}</span>
            </button>
          </li>
        ))}
      </ul>
    </main>
  );
}
