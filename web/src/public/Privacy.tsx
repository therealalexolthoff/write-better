// The privacy page, written for teachers: in plain language, what Write
// Better keeps, what goes to the AI provider, and who can see what. Not a
// legal document. Keep it true to how the app works (docs/REQUIREMENTS.md
// section 5, CLAUDE.md).
import { PublicLayout } from "../Layout";

export default function Privacy() {
  return (
    <PublicLayout>
      <article className="prose">
        <h1>Privacy</h1>
        <p className="lead">
          Write Better is a free tool for English teachers and their adult students. Here is what it keeps, what it
          sends to the AI, and who can see your students' work.
        </p>

        <h2>What Write Better keeps</h2>
        <ul>
          <li>
            <strong>About you:</strong> your name and email address, and the private notes you keep about your students.
          </li>
          <li>
            <strong>About your students:</strong> the username you choose with each student (not their full name), their
            writing, any photos of their handwritten pages, and the feedback on their work.
          </li>
        </ul>

        <h2>What goes to the AI</h2>
        <p>
          Feedback is drafted by an AI model (Anthropic's Claude, or Google's Gemini as a backup) running on Google Cloud
          in the United States. Before any student writing is sent:
        </p>
        <ul>
          <li>you remove names and personal details from a copy of it, and only that copy is sent;</li>
          <li>the student is identified only by a random code, never by their name or username;</li>
          <li>your notes about the student are never sent.</li>
        </ul>
        <p>
          Photos of handwritten pages are the one exception: they are sent as they are, so the AI can copy out the text.
          Ask students to write only their first name on paper.
        </p>
        <p>
          The AI providers don't use this writing to train their models. Google may keep requests for a short time to
          check for abuse.
        </p>

        <h2>Who can see student work</h2>
        <ul>
          <li>The student, and only once you have released the feedback.</li>
          <li>You. Teachers only ever see their own students.</li>
          <li>Not other students, not other teachers, and not the administrator, who manages accounts only.</li>
        </ul>

        <h2>Deleting data</h2>
        <p>
          You can delete a student at any time. That removes their account, their writing, their photos and your notes
          about them. Copies in the daily backups are gone within 7 days.
        </p>

        <h2>Everything else</h2>
        <ul>
          <li>No ads, and data is never sold.</li>
          <li>No tracking. The browser only stores what it needs to keep someone signed in.</li>
          <li>All data is stored on Google Cloud in the United States.</li>
        </ul>

        <p className="muted">Questions? Ask the Write Better administrator. Students can ask their teacher.</p>
      </article>
    </PublicLayout>
  );
}
