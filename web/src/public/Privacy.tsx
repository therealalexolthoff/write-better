// The privacy page: in plain language, what Write Better keeps, what goes
// to the AI provider, and who can see what. Not a legal document. Keep it
// true to how the app works (docs/REQUIREMENTS.md section 5, CLAUDE.md).
import { PublicLayout } from "../Layout";

export default function Privacy() {
  return (
    <PublicLayout>
      <article className="prose">
        <h1>Privacy</h1>
        <p className="lead">
          Write Better is a free tool for English teachers and their adult students. Here is what it keeps, what it
          sends to the AI, and who can see your work.
        </p>

        <h2>What Write Better keeps</h2>
        <ul>
          <li>
            <strong>Students:</strong> a username your teacher chooses with you (not your full name), your writing, any
            photos of your handwritten pages, and the feedback on your work.
          </li>
          <li>
            <strong>Teachers:</strong> your name and email address, and the private notes you keep about your students.
          </li>
        </ul>

        <h2>What goes to the AI</h2>
        <p>
          Feedback is drafted by an AI model (Anthropic's Claude, or Google's Gemini as a backup) running on Google Cloud
          in the United States. Before any writing is sent:
        </p>
        <ul>
          <li>your teacher removes names and personal details from a copy of it, and only that copy is sent;</li>
          <li>you are identified only by a random code, never by your name or username;</li>
          <li>your teacher's notes about you are never sent.</li>
        </ul>
        <p>
          Photos of handwritten pages are the one exception: they are sent as they are, so the AI can copy out the text.
          That is why students are asked to write only their first name on paper.
        </p>
        <p>
          The AI providers don't use your writing to train their models. Google may keep requests for a short time to
          check for abuse.
        </p>

        <h2>Who can see your work</h2>
        <ul>
          <li>You, and only once your teacher has released the feedback.</li>
          <li>Your teacher. Teachers only ever see their own students.</li>
          <li>Not other students, not other teachers, and not the administrator, who manages accounts only.</li>
        </ul>

        <h2>Deleting your data</h2>
        <p>
          Your teacher can delete your account at any time. That removes your account, your writing, your photos and
          their notes about you. Copies in the daily backups are gone within 7 days.
        </p>

        <h2>Everything else</h2>
        <ul>
          <li>No ads, and your data is never sold.</li>
          <li>No tracking. Your browser only stores what it needs to keep you signed in.</li>
          <li>All data is stored on Google Cloud in the United States.</li>
        </ul>

        <p className="muted">Questions? Students can ask their teacher. Teachers can ask the Write Better administrator.</p>
      </article>
    </PublicLayout>
  );
}
