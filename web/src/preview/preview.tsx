// Development-only preview of every screen with sample data, for design
// work and screenshots: http://localhost:5173/preview.html?screen=<name>
// (no ?screen= lists them). Not part of the production build (vite.config.ts
// builds index.html only) and never served by the API.
//
// It replaces fetch with canned API answers, so no API, database or sign-in
// is needed. All names and writing here are made up.
import { StrictMode, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import Pending from "../account/Pending";
import Setup, { AuthenticatorStep } from "../account/Setup";
import AdminApp from "../admin/AdminApp";
import { SignedIn } from "../App";
import { initAuth } from "../firebase";
import { AppHeader } from "../Layout";
import Login from "../Login";
import Home from "../public/Home";
import Privacy from "../public/Privacy";
import SignUp from "../public/SignUp";
import DoExercise from "../student/DoExercise";
import StudentApp from "../student/StudentApp";
import MyProgress from "../student/MyProgress";
import ClassesPanel from "../teacher/ClassesPanel";
import ExerciseScreen from "../teacher/ExerciseScreen";
import ProfilePanel from "../teacher/ProfilePanel";
import StudentsPanel from "../teacher/StudentsPanel";
import AssignWriting from "../teacher/AssignWriting";
import { AssignmentList, AssignmentScreen } from "../teacher/Assignments";
import "../styles.css";

// ---- sample data ----

const PROMPT = "Describe what you did last weekend. Who were you with, and what did you enjoy most?";
const TEXT =
  "Last weekend I go to the beach with my sister. We swimmed in the sea and eat ice cream. " +
  "it was a very fun day, and I want to go again next month.";

// Annotation offsets worked out from the text, the way the API does.
function at(text: string, words: string, occurrence = 1) {
  let start = -1;
  for (let i = 0; i < occurrence; i++) start = text.indexOf(words, start + 1);
  return { span_text: words, occurrence, start, end: start + words.length };
}
const ANNOTATIONS = [
  { code: "VT", correction: "went", explanation: "Past time needs the past tense.", ...at(TEXT, "go") },
  { code: "VF", correction: "swam", explanation: "The past of 'swim' is irregular.", ...at(TEXT, "swimmed") },
  { code: "VT", correction: "ate", explanation: "Keep the past tense.", ...at(TEXT, "eat") },
  { code: "CAP", correction: "It", explanation: "Sentences start with a capital letter.", ...at(TEXT, "it was") },
];
const EVALUATION = {
  annotations: ANNOTATIONS,
  comment: "A lively description. Watch your past tense: most of your mistakes are verbs that need to be in the past.",
};
const MEANINGS: Record<string, string> = { VT: "Verb tense", VF: "Verb form", CAP: "Capitalization", SP: "Spelling", ART: "Article/determiner", P: "Punctuation" };
const STUDENT_SPANS = ANNOTATIONS.map((a) => ({ start: a.start, end: a.end, code: a.code, meaning: MEANINGS[a.code] }));

// The revision: the student fixed two spans and got one wrong.
const EDITS = { "0": "went", "1": "swimed", "2": "ate" };
function revise(text: string, edits: Record<string, string>) {
  let revised = "";
  let from = 0;
  const changed: { index: string; start: number; end: number }[] = [];
  [...ANNOTATIONS.entries()]
    .sort((a, b) => a[1].start - b[1].start)
    .forEach(([i, a]) => {
      const edit = edits[String(i)];
      if (edit === undefined) return;
      revised += text.slice(from, a.start);
      changed.push({ index: String(i), start: revised.length, end: revised.length + edit.length });
      revised += edit;
      from = a.end;
    });
  return { revised_text: revised + text.slice(from), changed };
}
const REVISED = revise(TEXT, EDITS);
const OUTCOMES = { "0": "fixed", "1": "changed_wrongly", "2": "fixed" } as const;

const CLASSES = [
  { class_id: "c-tue", name: "Tuesday evening", archived: false, student_count: 3 },
  { class_id: "c-sat", name: "Saturday advanced", archived: false, student_count: 1 },
  { class_id: "c-old", name: "Summer intensive", archived: true, student_count: 0 },
];
const STUDENTS = [
  { student_id: "s1", username: "maria.k", active: true, class_id: "c-tue" },
  { student_id: "s2", username: "tomas.r", active: true, class_id: "c-tue" },
  { student_id: "s3", username: "aiko.s", active: true, class_id: "c-sat" },
  { student_id: "s4", username: "omar.h", active: false, class_id: "c-tue" },
];

// The student's own error view: counts over all returned work and the last 5.
function sentence(text: string, words: string) {
  const start = text.indexOf(words);
  return { text, start, end: start + words.length, cut_start: false, cut_end: false };
}
const MY_ERRORS = {
  pieces: 8,
  recent_pieces: 5,
  all: [
    { code: "VT", meaning: "Verb tense", errors: 11, fixed: 6, unfixed: 1, changed_wrongly: 2 },
    { code: "ART", meaning: "Article/determiner", errors: 7, fixed: 4, unfixed: 0, changed_wrongly: 1 },
    { code: "CAP", meaning: "Capitalization", errors: 4, fixed: 4, unfixed: 0, changed_wrongly: 0 },
    { code: "VF", meaning: "Verb form", errors: 3, fixed: 1, unfixed: 1, changed_wrongly: 1 },
    { code: "P", meaning: "Punctuation", errors: 1, fixed: 0, unfixed: 0, changed_wrongly: 0 },
  ],
  recent: [
    { code: "ART", meaning: "Article/determiner", errors: 4, fixed: 2, unfixed: 0, changed_wrongly: 1 },
    { code: "VT", meaning: "Verb tense", errors: 3, fixed: 2, unfixed: 0, changed_wrongly: 0 },
    { code: "VF", meaning: "Verb form", errors: 2, fixed: 1, unfixed: 1, changed_wrongly: 0 },
  ],
  examples: {
    VT: [
      { title: "My weekend", ...sentence("Last weekend I go to the beach with my sister.", "go") },
      { title: "A letter to a friend", ...sentence("Yesterday we watch a film at the cinema.", "watch") },
    ],
    ART: [{ title: "My hometown", ...sentence("My town has beautiful old church near the river.", "beautiful") }],
  },
};

function teacherExercise(state: string, extra: object = {}) {
  return {
    exercise_id: `ex-${state}`, student_id: "s1", kind: "writing", status: "assigned", title: "My weekend",
    teacher_request: "Written by you, for 3 students.", prompt: PROMPT, min_words: 50, max_words: 150, state,
    answers: { text: TEXT.replace("my sister.", "my sister Lucia.") }, scrubbed_answers: { text: TEXT }, evaluation: EVALUATION,
    evaluation_valid: true, photo_count: 0, transcription: null, final_source: "typed", revision: null, ...extra,
  };
}

function studentExercise(state: string, extra: object = {}) {
  return {
    exercise_id: `ex-${state}`, kind: "writing", title: "My weekend", state, answers: { text: "" },
    prompt: PROMPT, min_words: 50, max_words: 150, ...extra,
  };
}

const RESULTS = { answer_text: TEXT, spans: STUDENT_SPANS, comment: EVALUATION.comment };

const API: Record<string, unknown> = {
  "GET /signup/me": { status: "pending", email_verified: false },
  "GET /admin/signups": [
    { uid: "u-rosa", name: "Rosa Diaz", email: "rosa.diaz@example.com", email_verified: true, created_at: "2026-11-08T15:20:00Z" },
    { uid: "u-ben", name: "Ben Okafor", email: "ben.okafor@example.com", email_verified: false, created_at: "2026-11-09T09:05:00Z" },
  ],
  "GET /admin/teachers": [
    { uid: "t-ana", name: "Ana Lee", email: "ana.lee@example.com", active: true, student_count: 14 },
    { uid: "t-sam", name: "Sam Patel", email: "sam.patel@example.com", active: true, student_count: 9 },
    { uid: "t-joe", name: "Joe Martin", email: "joe.martin@example.com", active: false, student_count: 0 },
  ],
  "GET /config": { firebase: { apiKey: "preview", authDomain: "preview.example" } },
  "GET /students": STUDENTS,
  "GET /classes": CLASSES,
  "GET /assignments": [
    { assignment_id: "a-weekend", class_id: "c-tue", title: "My weekend", created_at: "2026-11-03T18:00:00Z", students: 3,
      progress: { not_started: 0, writing: 1, needs_you: 1, with_student: 0, done: 1 } },
    { assignment_id: "a-letter", class_id: "c-tue", title: "A letter to a friend", created_at: "2026-10-27T18:00:00Z", students: 3,
      progress: { not_started: 0, writing: 0, needs_you: 1, with_student: 1, done: 1 } },
    { assignment_id: "a-town", class_id: "c-sat", title: "My hometown", created_at: "2026-10-25T10:00:00Z", students: 1,
      progress: { not_started: 0, writing: 0, needs_you: 0, with_student: 0, done: 1 } },
  ],
  "GET /assignments/a-weekend": {
    assignment_id: "a-weekend", class_id: "c-tue", title: "My weekend", prompt: PROMPT, min_words: 50, max_words: 150,
    created_at: "2026-11-03T18:00:00Z", progress: { not_started: 0, writing: 1, needs_you: 1, with_student: 0, done: 1 },
    students: [
      { exercise_id: "ex-draft_ready", student_id: "s1", username: "maria.k", state: "draft_ready" },
      { exercise_id: "ex-r", student_id: "s4", username: "omar.h", state: "revision_reviewed" },
      { exercise_id: "ex-assigned", student_id: "s2", username: "tomas.r", state: "in_progress" },
    ],
    not_assigned: [{ student_id: "s5", username: "lina.m" }],
  },
  "GET /me/errors": MY_ERRORS,
  "GET /taxonomy": Object.entries(MEANINGS).map(([code, description]) => ({ code, description })),
  "GET /overview": [
    { student_id: "s1", username: "maria.k", work: [
      { exercise_id: "ex-draft_ready", title: "My weekend", state: "draft_ready" },
      { exercise_id: "ex-revision_submitted", title: "A letter to a friend", state: "revision_submitted" },
    ] },
    { student_id: "s2", username: "tomas.r", work: [{ exercise_id: "ex-assigned", title: "My weekend", state: "in_progress" }] },
    { student_id: "s3", username: "aiko.s", work: [] },
  ],
  "GET /exercises": [
    { exercise_id: "ex-draft_ready", title: "My weekend", status: "assigned", state: "draft_ready" },
    { exercise_id: "ex-revision_submitted", title: "A letter to a friend", status: "assigned", state: "revision_submitted" },
    { exercise_id: "ex-released", title: "My hometown", status: "assigned", state: "revision_reviewed" },
  ],
  "GET /students/s1/profile": {
    profile: { window: 5, submissions_counted: 4, codes: [
      { code: "VT", meaning: "Verb tense", errors: 9, fixed: 4, unfixed: 1, changed_wrongly: 1 },
      { code: "ART", meaning: "Article/determiner", errors: 5, fixed: 2, unfixed: 0, changed_wrongly: 0 },
      { code: "CAP", meaning: "Capitalization", errors: 3, fixed: 3, unfixed: 0, changed_wrongly: 0 },
      { code: "VF", meaning: "Verb form", errors: 2, fixed: 0, unfixed: 1, changed_wrongly: 1 },
    ] },
    teacher_notes: "Works in a hotel. Wants to write better emails to guests.",
  },
  "GET /exercises/ex-draft_ready": teacherExercise("draft_ready"),
  "GET /exercises/ex-revision_submitted": teacherExercise("revision_submitted", {
    title: "A letter to a friend",
    revision: { edits: EDITS, submitted_at: "2026-11-08T10:00:00Z", outcomes: {}, ...REVISED },
  }),
  "GET /me/exercises": [
    { exercise_id: "ex-in_progress", title: "My weekend", state: "in_progress" },
    { exercise_id: "ex-revision_open", title: "A letter to a friend", state: "revision_open" },
    { exercise_id: "ex-revision_reviewed", title: "My hometown", state: "revision_reviewed" },
    { exercise_id: "ex-scrub_review", title: "My favourite food", state: "scrub_review" },
  ],
  "GET /exercises/ex-in_progress": studentExercise("in_progress", {
    answers: { text: "Last weekend I go to the beach with my sister. We swimmed in the sea" },
  }),
  "GET /exercises/ex-revision_open": studentExercise("revision_open", { ...RESULTS, revision_edits: { "0": "went" } }),
  "GET /exercises/ex-revision_reviewed": studentExercise("revision_reviewed", {
    ...RESULTS, revision_edits: EDITS, revised_text: REVISED.revised_text, outcomes: OUTCOMES, corrections: { "1": "swam" },
  }),
};

window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
  const url = new URL(String(input), window.location.origin);
  const key = `${init?.method ?? "GET"} ${url.pathname}`;
  if (key.endsWith("/photos")) return Response.json([]);
  if (!(key in API)) return Response.json({ status: "ok" });
  return Response.json(API[key]);
};

// ---- screens ----

const noop = () => {};

function Teacher({ children }: { children: ReactNode }) {
  return (
    <div className="app">
      <AppHeader role="teacher" onSignOut={noop} />
      {children}
    </div>
  );
}

const SCREENS: Record<string, () => ReactNode> = {
  home: () => <Home />,
  privacy: () => <Privacy />,
  "sign-in": () => <Login />,
  "sign-up": () => <SignUp signedIn={false} />,
  pending: () => <div className="app"><AppHeader role="unknown" onSignOut={noop} /><Pending email="rosa.diaz@example.com" /></div>,
  "setup-email": () => <div className="app"><AppHeader role="teacher" onSignOut={noop} /><Setup email="rosa.diaz@example.com" emailVerified={false} /></div>,
  "setup-authenticator": () => (
    <div className="app">
      <AppHeader role="teacher" onSignOut={noop} />
      <main className="page narrow">
        <h1>Set up your account</h1>
        <p className="lead">Two quick steps keep your students' work safe. You only do this once.</p>
        <ol className="progress"><li className="done">Verify your email</li><li className="current">Authenticator app</li></ol>
        <AuthenticatorStep initial={{ key: "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP", url: "otpauth://totp/Write%20Better:rosa" }} />
      </main>
    </div>
  ),
  "teacher-overview": () => <Teacher><SignedIn session={{ role: "teacher", email: "ana@example.com", emailVerified: true, withCode: true }} /></Teacher>,
  "teacher-review": () => <Teacher><ExerciseScreen exerciseId="ex-draft_ready" onBack={noop} /></Teacher>,
  "teacher-revision": () => <Teacher><ExerciseScreen exerciseId="ex-revision_submitted" onBack={noop} /></Teacher>,
  "teacher-profile": () => (
    <Teacher><main className="page wide"><h1>maria.k</h1><ProfilePanel studentId="s1" /></main></Teacher>
  ),
  "teacher-assign": () => (
    <Teacher><main className="page wide"><AssignWriting classes={CLASSES.filter((c) => !c.archived)} classId="c-tue" students={STUDENTS.filter((s) => s.active)} onDone={noop} /></main></Teacher>
  ),
  "teacher-students": () => (
    <Teacher><main className="page wide"><StudentsPanel students={STUDENTS} classes={CLASSES} classId="" onChange={noop} /></main></Teacher>
  ),
  "teacher-assignments": () => (
    <Teacher><main className="page wide"><h1>All classes</h1><AssignmentList classId="" classes={CLASSES} onOpen={noop} /></main></Teacher>
  ),
  "teacher-assignment": () => (
    <Teacher>
      <AssignmentScreen assignmentId="a-weekend" className={(id) => CLASSES.find((c) => c.class_id === id)?.name ?? ""} onBack={noop} onOpenExercise={noop} />
    </Teacher>
  ),
  "teacher-classes": () => <Teacher><main className="page wide"><ClassesPanel classes={CLASSES} onChange={noop} /></main></Teacher>,
  "teacher-first-run": () => (
    <Teacher>
      <main className="page narrow">
        <h1>Welcome to Write Better</h1>
        <p className="lead">Start by creating a class. Then add your students to it and assign them some writing.</p>
        <ClassesPanel classes={[]} onChange={noop} firstRun />
      </main>
    </Teacher>
  ),
  "student-progress": () => <div className="app"><AppHeader role="student" onSignOut={noop} /><StudentApp initialTab="progress" /></div>,
  "student-progress-open": () => (
    <div className="app">
      <AppHeader role="student" onSignOut={noop} />
      <main className="page narrow"><h1>My progress</h1><MyProgress initialOpen="VT" /></main>
    </div>
  ),
  "student-home": () => <div className="app"><AppHeader role="student" onSignOut={noop} /><StudentApp /></div>,
  "student-writing": () => (
    <div className="app"><AppHeader role="student" onSignOut={noop} /><DoExercise exerciseId="ex-in_progress" onBack={noop} /></div>
  ),
  "student-revise": () => (
    <div className="app"><AppHeader role="student" onSignOut={noop} /><DoExercise exerciseId="ex-revision_open" onBack={noop} /></div>
  ),
  "student-checked": () => (
    <div className="app"><AppHeader role="student" onSignOut={noop} /><DoExercise exerciseId="ex-revision_reviewed" onBack={noop} /></div>
  ),
  "admin-signups": () => <div className="app"><AppHeader role="admin" onSignOut={noop} /><AdminApp /></div>,
  "admin-teachers": () => <div className="app"><AppHeader role="admin" onSignOut={noop} /><AdminApp initialTab="teachers" /></div>,
};

function Index() {
  return (
    <main className="page narrow">
      <h1>Screen preview</h1>
      <ul>
        {Object.keys(SCREENS).map((name) => (
          <li key={name}><a href={`?screen=${name}`}>{name}</a></li>
        ))}
      </ul>
    </main>
  );
}

// ?width=390 shows the screen in a frame exactly that wide, for phone-sized
// screenshots (headless Chrome won't make a window narrower than ~500px).
function Framed({ name, width }: { name: string; width: number }) {
  return (
    <iframe
      title={name}
      src={`?screen=${name}`}
      style={{ width, height: "100vh", border: 0, display: "block", margin: "0 auto" }}
    />
  );
}

const params = new URLSearchParams(window.location.search);
const name = params.get("screen") ?? "";
const width = Number(params.get("width"));
const known = name in SCREENS;
initAuth().then(() => {
  const body = known && width ? <Framed name={name} width={width} /> : known ? SCREENS[name]() : <Index />;
  createRoot(document.getElementById("root")!).render(<StrictMode>{body}</StrictMode>);
});
