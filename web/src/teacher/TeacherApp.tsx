// Teacher home (laptop-first): pick a class (or all of them), then see its
// overview, its assignments, or one student's writing and profile & notes.
// Also assigns writing and manages classes and student accounts.
import { useEffect, useState } from "react";
import { api } from "../api";
import type { ClassInfo, ExerciseSummary, Student } from "../types";
import AssignWriting from "./AssignWriting";
import { AssignmentList, AssignmentScreen } from "./Assignments";
import ClassesPanel from "./ClassesPanel";
import ExerciseScreen, { stateLabel } from "./ExerciseScreen";
import Overview from "./Overview";
import ProfilePanel from "./ProfilePanel";
import StudentsPanel from "./StudentsPanel";

type Tab = "exercises" | "profile";
const TABS: { tab: Tab; label: string }[] = [
  { tab: "exercises", label: "Writing" },
  { tab: "profile", label: "Profile & notes" },
];
type Panel = "" | "writing" | "students" | "classes";
type View = "overview" | "assignments";

export default function TeacherApp() {
  const [classes, setClasses] = useState<ClassInfo[] | null>(null);
  const [students, setStudents] = useState<Student[]>([]);
  const [classId, setClassId] = useState(""); // "" = all classes
  const [studentId, setStudentId] = useState(""); // "" = the overview
  const [tab, setTab] = useState<Tab>("exercises");
  const [view, setView] = useState<View>("overview");
  const [openExercise, setOpenExercise] = useState<string | null>(null);
  const [openAssignment, setOpenAssignment] = useState<string | null>(null);
  const [panel, setPanel] = useState<Panel>("");
  const [message, setMessage] = useState("");
  // Bumped after assigning writing or changing students, so the overview reloads.
  const [overviewKey, setOverviewKey] = useState(0);

  const loadClasses = () => api<ClassInfo[]>("/classes").then(setClasses);
  const loadStudents = () => api<Student[]>("/students").then(setStudents);
  const reload = () => {
    loadClasses();
    loadStudents();
    setOverviewKey((k) => k + 1);
  };
  useEffect(() => {
    loadClasses();
    loadStudents();
  }, []);

  if (openExercise) return <ExerciseScreen exerciseId={openExercise} onBack={() => setOpenExercise(null)} />;
  if (classes === null) return <p className="loading">Loading…</p>;
  const className = (id: string) => classes.find((c) => c.class_id === id)?.name ?? "";
  if (openAssignment) {
    return (
      <AssignmentScreen
        assignmentId={openAssignment}
        className={className}
        onBack={() => setOpenAssignment(null)}
        onOpenExercise={setOpenExercise}
      />
    );
  }

  const openClasses = classes.filter((c) => !c.archived);
  const archived = classes.filter((c) => c.archived);
  const current = classes.find((c) => c.class_id === classId);
  const inView = students.filter((s) => !classId || s.class_id === classId);
  const active = inView.filter((s) => s.active);
  const student = active.find((s) => s.student_id === studentId);
  const toggle = (next: Panel) => {
    setPanel(panel === next ? "" : next);
    setMessage("");
  };
  const pickClass = (id: string) => {
    setClassId(id);
    setStudentId("");
  };

  if (classes.length === 0) {
    return (
      <main className="page narrow">
        <h1>Welcome to Write Better</h1>
        <p className="lead">Start by creating a class. Then add your students to it and assign them some writing.</p>
        <ClassesPanel classes={[]} onChange={reload} firstRun />
      </main>
    );
  }

  return (
    <main className="page wide">
      <div className="row spread">
        <h1>{student ? student.username : current ? current.name : "All classes"}</h1>
        <div className="row">
          <button className={panel === "writing" ? "" : "primary"} onClick={() => toggle("writing")}>
            {panel === "writing" ? "Close writing form" : "Assign writing"}
          </button>
          <button onClick={() => toggle("students")}>{panel === "students" ? "Hide students" : "Manage students"}</button>
          <button onClick={() => toggle("classes")}>{panel === "classes" ? "Hide classes" : "Manage classes"}</button>
        </div>
      </div>

      <div className="row pickers">
        <label>
          Class{" "}
          <select value={classId} onChange={(e) => pickClass(e.target.value)}>
            <option value="">All classes</option>
            {openClasses.map((c) => <option key={c.class_id} value={c.class_id}>{c.name}</option>)}
            {archived.length > 0 && (
              <optgroup label="Archived">
                {archived.map((c) => <option key={c.class_id} value={c.class_id}>{c.name}</option>)}
              </optgroup>
            )}
          </select>
        </label>
        <label>
          Show{" "}
          <select value={studentId} onChange={(e) => setStudentId(e.target.value)}>
            <option value="">{current ? "Class overview" : "Overview"}</option>
            {active.map((s) => (
              <option key={s.student_id} value={s.student_id}>{s.username}</option>
            ))}
          </select>
        </label>
        {current?.archived && <span className="badge">Archived class</span>}
      </div>

      {panel === "classes" && <ClassesPanel classes={classes} onChange={reload} />}
      {panel === "students" && (
        <StudentsPanel students={inView} classes={classes} classId={classId} onChange={reload} />
      )}
      {panel === "writing" && (
        <AssignWriting
          classes={openClasses}
          classId={classId}
          students={students.filter((s) => s.active)}
          onDone={(done, assignmentId) => {
            setPanel("");
            setMessage(done);
            setView("assignments");
            setOverviewKey((k) => k + 1);
            setOpenAssignment(assignmentId);
          }}
        />
      )}
      {message && <p className="notice">{message}</p>}

      {!student ? (
        <>
          <div className="tabs" role="tablist">
            <button role="tab" aria-selected={view === "overview"} className={view === "overview" ? "active" : ""} onClick={() => setView("overview")}>
              Students
            </button>
            <button role="tab" aria-selected={view === "assignments"} className={view === "assignments" ? "active" : ""} onClick={() => setView("assignments")}>
              Assignments
            </button>
          </div>
          {view === "overview" ? (
            <Overview key={`${classId}-${overviewKey}`} classId={classId} onOpenExercise={setOpenExercise} onOpenStudent={setStudentId} />
          ) : (
            <AssignmentList key={`${classId}-${overviewKey}`} classId={classId} classes={classes} onOpen={setOpenAssignment} />
          )}
        </>
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
