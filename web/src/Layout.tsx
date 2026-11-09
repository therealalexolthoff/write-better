// The frame around every page: the Write Better wordmark, a header, and
// (on public pages) a footer. Public pages and the signed-in app share it.
import type { ReactNode } from "react";
import { Link, PATHS } from "./router";

export function Wordmark() {
  return (
    <span className="wordmark" aria-label="Write Better">
      <span aria-hidden="true">
        Write <span className="wordmark-better">Better</span>
      </span>
    </span>
  );
}

export function PublicLayout({ children }: { children: ReactNode }) {
  return (
    <div className="site">
      <header className="site-header">
        <div className="site-header-inner">
          <Link to={PATHS.home} className="home-link">
            <Wordmark />
          </Link>
          <nav className="site-nav" aria-label="Main">
            <Link to={PATHS.privacy}>Privacy</Link>
            <Link to={PATHS.signIn} className="button primary small">Sign in</Link>
          </nav>
        </div>
      </header>
      <main className="site-main">{children}</main>
      <footer className="site-footer">
        <div className="site-footer-inner">
          <Wordmark />
          <p>Clear, teacher-checked feedback on English writing. Free to use.</p>
          <nav aria-label="Footer">
            <Link to={PATHS.home}>Home</Link>
            <Link to={PATHS.privacy}>Privacy</Link>
            <Link to={PATHS.signIn}>Sign in</Link>
          </nav>
        </div>
      </footer>
    </div>
  );
}

const ROLE_LABELS: Record<string, string> = { admin: "Admin", teacher: "Teacher", student: "Student" };

// The signed-in app's header: wordmark, who you are, and sign out.
export function AppHeader({ role, onSignOut }: { role: string; onSignOut: () => void }) {
  return (
    <header className="app-header">
      <div className="app-header-inner">
        <Wordmark />
        <div className="row">
          {ROLE_LABELS[role] && <span className="role-chip">{ROLE_LABELS[role]}</span>}
          <button className="link" onClick={onSignOut}>Sign out</button>
        </div>
      </div>
    </header>
  );
}
