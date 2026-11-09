// Teacher home (laptop-first): the class overview, or one student's
// writing and profile & notes. Also assigns writing and manages student
// accounts.
import { useEffect, useState } from "react";
import { api } from "../api";
import type { ExerciseSummary, Student } from "../types";
import ExerciseScreen, { stateLabel } from "./ExerciseScreen";
import Overview from "./Overview";
import ProfilePanel from "./ProfilePanel";
import StudentsPanel from "./StudentsPanel";
import WritingForStudents from "./WritingForStudents";

type Tab = "exercises" | "profile";
const TABS: { tab: Tab; label: string }[] = [
  { tab: "exercises", label: "Writing" },
  { tab: "profile", label: "Profile & notes" },
];

export default function TeacherApp() {
  const [students, setStudents] = useState<Student[]>([]);
  const [studentId, setStudentId] = useState(""); // "" = class overview
  const [tab, setTab] = useState<Tab>("exercises");
  const [openExercise, setOpenExercise] = useState<string | null>(null);
  const [showStudents, setShowStudents] = useState(false);
  const [showWriting, setShowWriting] = useState(false);
  const [message, setMessage] = useState("");
  // Bumped after assigning writing, so the overview reloads.
  const [overviewKey, setOverviewKey] = useState(0);

  const loadStudents = () => api<Student[]>("/students").then(setStudents);
  useEffect(() => {
    loadStudents();
  }, []);

  if (openExercise) return <ExerciseScreen exerciseId={openExercise} onBack={() => setOpenExercise(null)} />;

  const active = students.filter((s) => s.active);
  const student = active.find((s) => s.student_id === studentId);
  return (
    <main className="page wide">
      <div className="row spread">
        <h1>{student ? student.username : "Class overview"}</h1>
        <div className="row">
          <button onClick={() => { setShowWriting(!showWriting); setMessage(""); }}>
            {showWriting ? "Close writing form" : "Assign writing"}
          </button>
          <button onClick={() => setShowStudents(!showStudents)}>{showStudents ? "Hide students" : "Manage students"}</button>
        </div>
      </div>
      {showStudents && <StudentsPanel students={students} onChange={loadStudents} />}
      {showWriting && (
        <WritingForStudents
          students={active}
          onDone={(done) => {
            setShowWriting(false);
            setMessage(done);
            setOverviewKey((k) => k + 1);
          }}
        />
      )}
      {message && <p className="notice">{message}</p>}
      <label>
        Show{" "}
        <select value={studentId} onChange={(e) => setStudentId(e.target.value)}>
          <option value="">Class overview</option>
          {active.map((s) => (
            <option key={s.student_id} value={s.student_id}>{s.username}</option>
          ))}
        </select>
      </label>

      {!student ? (
        <Overview key={overviewKey} onOpenExercise={setOpenExercise} onOpenStudent={setStudentId} />
      ) : (
        <>
          <div className="tabs" role="tablist">
            {TABS.map((t) => (
              <button key={t.tab} role="tab" aria-selected={tab === t.tab} className={tab === t.tab ? "active" : ""} onClick={() => setTab(t.tab)}>
                {t.label}
              </button>
            ))}
          </div>
          {tab === "exercises" && <StudentExercises key={studentId} studentId={studentId} onOpen={setOpenExercise} />}
          {tab === "profile" && <ProfilePanel key={studentId} studentId={studentId} />}
        </>
      )}
    </main>
  );
}

function StudentExercises({ studentId, onOpen }: { studentId: string; onOpen: (id: string) => void }) {
  const [list, setList] = useState<ExerciseSummary[] | null>(null);

  useEffect(() => {
    api<ExerciseSummary[]>(`/exercises?student_id=${encodeURIComponent(studentId)}`).then(setList);
  }, [studentId]);

  return (
    <>
      <table>
        <thead>
          <tr><th>Title</th><th>Stage</th></tr>
        </thead>
        <tbody>
          {list?.map((ex) => (
            <tr key={ex.exercise_id} className="clickable" onClick={() => onOpen(ex.exercise_id)}>
              <td>{ex.title}</td>
              <td>{stateLabel(ex.state)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {list?.length === 0 && <p>No writing for this student yet. Use “Assign writing” to give them some.</p>}
    </>
  );
}
