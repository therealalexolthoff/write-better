// One writing exercise, teacher side: the whole pipeline (WritingReview),
// releasing results, and reopening.
import { useEffect, useState } from "react";
import { api } from "../api";
import type { TeacherExercise } from "../types";
import WritingReview from "./WritingReview";

export function stateLabel(state: string): string {
  const labels: Record<string, string> = {
    assigned: "Assigned",
    in_progress: "In progress",
    transcribing: "Transcribing photos",
    transcript_review: "Awaiting transcription review",
    scrub_review: "Submitted – awaiting scrub",
    evaluating: "Evaluating",
    draft_ready: "Draft evaluation ready",
    ready_to_release: "Ready to release",
    released: "Released",
    revision_open: "Released – revision open",
    revision_submitted: "Revision submitted",
    revision_reviewed: "Revision checked – sent to student",
  };
  return labels[state] ?? state;
}

export default function ExerciseScreen({ exerciseId, onBack }: { exerciseId: string; onBack: () => void }) {
  const [exercise, setExercise] = useState<TeacherExercise | null>(null);
  const [error, setError] = useState("");
  const [paused, setPaused] = useState("");

  useEffect(() => {
    api<TeacherExercise>(`/exercises/${exerciseId}`).then(setExercise, (err) => setError(err.message));
    // Whether the monthly AI cap has paused feedback (api/app/exercises.py).
    api<{ paused: boolean; message: string }>("/ai-status").then((s) => setPaused(s.paused ? s.message : ""), () => {});
  }, [exerciseId]);

  return (
    <main className="page wide">
      <button className="link" onClick={onBack}>← All exercises</button>
      {error && <p className="error">{error}</p>}
      {paused && (
        <p className="confirm" role="status">
          <strong>{paused.split(". ")[0]}.</strong> {paused.split(". ").slice(1).join(". ")}
        </p>
      )}
      {exercise && <Review exercise={exercise} onChange={setExercise} />}
    </main>
  );
}

// ---- the pipeline, release, reopen ----

function Review({ exercise, onChange }: { exercise: TeacherExercise; onChange: (e: TeacherExercise) => void }) {
  const [confirmReopen, setConfirmReopen] = useState(false);
  const [error, setError] = useState("");

  async function act(path: string) {
    setError("");
    try {
      onChange(await api(`/exercises/${exercise.exercise_id}/${path}`, "POST"));
      setConfirmReopen(false);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <>
      <h1>{exercise.title}</h1>
      <p>
        <span className="muted">Stage:</span> <span className="stage yours">{stateLabel(exercise.state)}</span>
      </p>
      <WritingReview exercise={exercise} onChange={onChange} />

      {error && <p className="error">{error}</p>}
      <div className="row">
        {exercise.state === "ready_to_release" && (
          <button className="primary" onClick={() => act("release")}>Release results to student</button>
        )}
        {["transcript_review", "scrub_review", "draft_ready", "ready_to_release"].includes(exercise.state) &&
          (confirmReopen ? (
            <>
              <span>Send this back to the student to keep working? (This is recorded in the audit log.)</span>
              <button onClick={() => act("reopen")}>Yes, reopen</button>
              <button onClick={() => setConfirmReopen(false)}>Cancel</button>
            </>
          ) : (
            <button onClick={() => setConfirmReopen(true)}>Reopen…</button>
          ))}
      </div>
    </>
  );
}
