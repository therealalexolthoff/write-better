// Top level: picks the page from the address bar. Public pages (home,
// privacy) show straight away. Sign-in and the app wait for Identity
// Platform, then the app shows the admin, teacher or student screens from
// the role claim the API set on the account.
import { useEffect, useState } from "react";
import { onIdTokenChanged } from "firebase/auth";
import { initAuth, logOut } from "./firebase";
import { AppHeader, PublicLayout } from "./Layout";
import Login from "./Login";
import Home from "./public/Home";
import Privacy from "./public/Privacy";
import { Link, PATHS, navigate, usePath } from "./router";
import StudentApp from "./student/StudentApp";
import TeacherApp from "./teacher/TeacherApp";

type Role = "admin" | "teacher" | "student" | "unknown";
type Session = { role: Role } | null;
const ROLES: Role[] = ["admin", "teacher", "student"];

export default function App() {
  const path = usePath();
  if (path === PATHS.home) return <Home />;
  if (path === PATHS.privacy) return <Privacy />;
  if (path === PATHS.signIn || path === PATHS.app) return <SignedInArea path={path} />;
  return <NotFound />;
}

// Sign-in and the app: both need to know whether someone is signed in.
function SignedInArea({ path }: { path: string }) {
  const [session, setSession] = useState<Session | undefined>(undefined);
  const [error, setError] = useState("");

  useEffect(() => {
    let unsubscribe = () => {};
    initAuth()
      .then((auth) => {
        unsubscribe = onIdTokenChanged(auth, async (user) => {
          if (!user) return setSession(null);
          const { claims } = await user.getIdTokenResult();
          const role = ROLES.includes(claims.role as Role) ? (claims.role as Role) : "unknown";
          setSession({ role });
        });
      })
      .catch(() => setError("Could not reach Write Better. Check your connection and reload the page."));
    return () => unsubscribe();
  }, []);

  // Signed in on the sign-in page: go to the app. Signed out in the app: sign in.
  useEffect(() => {
    if (session && path === PATHS.signIn) navigate(PATHS.app, { replace: true });
    if (session === null && path === PATHS.app) navigate(PATHS.signIn, { replace: true });
  }, [session, path]);

  if (error) return <PublicLayout><div className="auth-page"><p className="error" role="alert">{error}</p></div></PublicLayout>;
  if (session === undefined) return <p className="loading" aria-live="polite">Loading…</p>;
  if (path === PATHS.signIn || session === null) return <Login />;

  return (
    <div className="app">
      <AppHeader role={session.role} onSignOut={() => logOut()} />
      <SignedIn role={session.role} />
    </div>
  );
}

export function SignedIn({ role }: { role: Role }) {
  if (role === "teacher") return <TeacherApp />;
  if (role === "student") return <StudentApp />;
  if (role === "admin") {
    return (
      <main className="page narrow">
        <h1>Admin</h1>
        <p className="notice">You're signed in as the admin. The admin screens are on their way.</p>
      </main>
    );
  }
  return (
    <main className="page narrow">
      <h1>Your account isn't ready yet</h1>
      <p className="notice">Your account hasn't been set up. If you're a student, ask your teacher.</p>
    </main>
  );
}

function NotFound() {
  return (
    <PublicLayout>
      <div className="auth-page">
        <h1>Page not found</h1>
        <p>That page doesn't exist.</p>
        <Link to={PATHS.home} className="button primary">Go to the home page</Link>
      </div>
    </PublicLayout>
  );
}
