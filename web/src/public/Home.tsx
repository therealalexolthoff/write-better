// The public home page, written for teachers: what Write Better does for
// them and their class, and how it works.
import { PublicLayout } from "../Layout";
import { Link, PATHS } from "../router";

const STEPS = [
  {
    title: "Set a writing task",
    text: "Write your own prompt, with word limits if you like, and assign it to your whole group or chosen students.",
  },
  {
    title: "Students write",
    text: "They type on a phone or computer, or write on paper and photograph each page. The AI copies out handwriting for you to check.",
  },
  {
    title: "Review the AI's draft",
    text: "Remove names first, then the AI marks each error with one of 14 codes. Accept, edit, recode or remove every mark, then release.",
  },
  {
    title: "Students correct their work",
    text: "Students get one chance to correct each marked part. You mark each correction, and they see how they did.",
  },
];

const REASONS = [
  {
    title: "You stay in control",
    text: "The AI only drafts. Nothing reaches a student until you have reviewed and approved it.",
  },
  {
    title: "Focused on accuracy",
    text: "Grammar, punctuation, spelling and capitalization only. No comments on style or content, and no scores or grades.",
  },
  {
    title: "See each student's patterns",
    text: "A profile for every student shows their most common errors and how their corrections went, from work you approved.",
  },
  {
    title: "Private by design",
    text: "Names come out before any writing goes to the AI. You only see your own students, and your notes stay private.",
  },
];

export default function Home() {
  return (
    <PublicLayout>
      <section className="hero">
        <div className="hero-inner">
          <p className="eyebrow">For teachers of adult English learners</p>
          <h1>Clear writing feedback for every student, checked by you.</h1>
          <p className="lead">
            Write Better drafts feedback on your students' grammar, punctuation, spelling and capitalization. You review
            and edit every suggestion before they see it, and they correct their own mistakes.
          </p>
          <div className="row">
            <Link to={PATHS.signIn} className="button primary large">Sign in</Link>
            <a href="#how-it-works" className="button large">How it works</a>
          </div>
          <p className="hero-note muted">Free to use. Students: sign in with the username your teacher gave you.</p>
        </div>
      </section>

      <section className="section" id="how-it-works">
        <div className="section-inner">
          <h2>How it works</h2>
          <ol className="steps">
            {STEPS.map((step, i) => (
              <li key={step.title}>
                <span className="step-number" aria-hidden="true">{i + 1}</span>
                <h3>{step.title}</h3>
                <p>{step.text}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="section tinted">
        <div className="section-inner">
          <h2>Why teachers use it</h2>
          <ul className="promises">
            {REASONS.map((reason) => (
              <li key={reason.title}>
                <h3>{reason.title}</h3>
                <p>{reason.text}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="section">
        <div className="section-inner split">
          <div>
            <h2>Simple for your students</h2>
            <p>
              You create each student's account and give them a username. They sign in on any phone or computer, see
              their tasks, and get their results with each mistake marked by its type. Large text, plain English, and
              their work saves as they go.
            </p>
          </div>
          <div>
            <h2>Free to use</h2>
            <p>
              Write Better is free for teachers and students. You only ever see your own students, and their data stays on
              Google Cloud in the United States. <Link to={PATHS.privacy}>How we handle data</Link>
            </p>
          </div>
        </div>
      </section>
    </PublicLayout>
  );
}
