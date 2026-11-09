// The public home page: what Write Better does and how it works.
import { PublicLayout } from "../Layout";
import { Link, PATHS } from "../router";

const STEPS = [
  {
    title: "Your teacher sets a writing task",
    text: "A short email, a story about your weekend, an opinion: whatever fits your class.",
  },
  {
    title: "You write it",
    text: "Type on your phone or computer, or write on paper and take a photo of each page. Your work saves as you go.",
  },
  {
    title: "Your teacher checks the feedback",
    text: "AI suggests where the mistakes are. Your teacher reviews every suggestion, then sends your results.",
  },
  {
    title: "You fix your mistakes",
    text: "Each mistake is marked with its type. Tap it, correct it, and see how you did.",
  },
];

const PROMISES = [
  {
    title: "Checked by a teacher",
    text: "The AI only drafts. Nothing reaches a student until their teacher has reviewed and approved it.",
  },
  {
    title: "Focused on accuracy",
    text: "Grammar, punctuation, spelling and capitalization: the mistakes that matter most when you write in English.",
  },
  {
    title: "No scores or grades",
    text: "Students see what to fix and how their corrections went. Never a number or a percentage.",
  },
  {
    title: "Private by design",
    text: "Names and personal details are removed before any writing goes to the AI. Teachers only ever see their own students.",
  },
];

export default function Home() {
  return (
    <PublicLayout>
      <section className="hero">
        <div className="hero-inner">
          <p className="eyebrow">Writing feedback for adult English learners</p>
          <h1>Write better English, one piece at a time.</h1>
          <p className="lead">
            Write Better gives students clear feedback on grammar, punctuation, spelling and capitalization, checked by
            their teacher before they see it.
          </p>
          <div className="row">
            <Link to={PATHS.signIn} className="button primary large">Sign in</Link>
            <a href="#how-it-works" className="button large">How it works</a>
          </div>
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
          <h2>Built around the teacher</h2>
          <ul className="promises">
            {PROMISES.map((promise) => (
              <li key={promise.title}>
                <h3>{promise.title}</h3>
                <p>{promise.text}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="section">
        <div className="section-inner split">
          <div>
            <h2>For students</h2>
            <p>
              Your teacher creates your account and tells you your username. Sign in on any phone or computer to see
              your writing tasks and your results.
            </p>
          </div>
          <div>
            <h2>For teachers</h2>
            <p>
              Assign writing to your class, review AI-drafted feedback in one place, and see each student's most
              common mistakes over time. Write Better is free to use.
            </p>
          </div>
        </div>
      </section>
    </PublicLayout>
  );
}
