// Shapes returned by the API. The Python models in api/app/models.py and
// shared/schemas.py are the source of truth; these mirror them.

// The student's response is stored under the one key "text".
export type Answers = Record<string, string>;

// An annotation as the API stores it: start/end are computed by the API.
export type Annotation = {
  code: string;
  span_text: string;
  occurrence: number;
  correction: string;
  explanation: string;
  start?: number;
  end?: number;
};

export type WritingEvaluation = { annotations: Annotation[]; comment: string };

export type Outcome = "fixed" | "unfixed" | "changed_wrongly";
// The student's revision as the teacher sees it. Keys are span indexes:
// positions in the evaluation's annotation list.
export type Revision = {
  edits: Record<string, string>;
  submitted_at: string | null;
  outcomes: Record<string, Outcome>;
  revised_text: string;
  changed: { index: string; start: number; end: number }[];
};

export type TeacherExercise = {
  exercise_id: string;
  student_id: string;
  kind: "writing";
  status: "assigned";
  title: string;
  teacher_request: string;
  prompt: string;
  min_words: number | null;
  max_words: number | null;
  state: string;
  answers: Answers;
  scrubbed_answers: Record<string, string>;
  evaluation: WritingEvaluation | null;
  evaluation_valid: boolean;
  photo_count: number;
  transcription: string | null;
  final_source: "typed" | "photo" | null;
  revision: Revision | null;
};

export type ExerciseSummary = { exercise_id: string; title: string; status?: string; state: string };
export type Student = { student_id: string; username: string; active: boolean; class_id: string | null };
export type ClassInfo = { class_id: string; name: string; archived: boolean; student_count: number };

// The student's own error view (api/app/progress.py).
export type ErrorExample = { title: string; text: string; start: number; end: number; cut_start: boolean; cut_end: boolean };
export type MyErrors = {
  pieces: number;
  recent_pieces: number;
  all: ProfileRow[];
  recent: ProfileRow[];
  examples: Record<string, ErrorExample[]>;
};
export type Code = { code: string; description: string };

export type StudentSpan = { start: number; end: number; code: string; meaning: string };

export type StudentExercise = {
  exercise_id: string;
  kind: "writing";
  title: string;
  state: string;
  answers: Answers;
  prompt: string;
  min_words?: number;
  max_words?: number;
  // After release:
  answer_text?: string;
  spans?: StudentSpan[]; // in annotation order: revision edits refer to these positions
  comment?: string;
  revision_edits?: Record<string, string>;
  revised_text?: string;
  // Once the teacher sends back the checked revision:
  outcomes?: Record<string, Outcome>; // only spans the student changed
  corrections?: Record<string, string>; // only spans not fixed
};

// ---- learner profile and overview ----

export type ProfileRow = {
  code: string;
  meaning: string;
  errors: number;
  fixed: number;
  unfixed: number;
  changed_wrongly: number;
};
export type StudentProfile = {
  profile: { window: number; submissions_counted: number; codes: ProfileRow[] };
  teacher_notes: string;
};

export type OverviewRow = {
  student_id: string;
  username: string;
  work: { exercise_id: string; title: string; state: string }[];
};
