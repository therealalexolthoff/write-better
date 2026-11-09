// Top level: picks the page from the address bar. Public pages (home,
// privacy) show straight away. Sign-in, sign-up and the app wait for
// Identity Platform. In the app:
// - an account with no role is a teacher sign-up waiting for approval;
// - a teacher or the admin signed in without an authenticator code is
//   still setting up their account (verify email, add the app);
// - otherwise the role picks the admin, teacher or student screens.
import { useEffect, useState } from "react";
import { onIdTokenChanged } from "firebase/auth";
import { initAuth, logOut } from "./firebase";
import Pending from "./account/Pending";
import Setup from "./account/Setup";
import AdminApp from "./admin/AdminApp";
import { AppHeader, PublicLayout } from "./Layout";
import Login from "./Login";
import Home from "./public/Home";
import Privacy from "./public/Privacy";
import SignUp from "./public/SignUp";
import { Link, PATHS, navigate, usePath } from "./router";
import StudentApp from "./student/StudentApp";
import TeacherApp from "./teacher/TeacherApp";

type Role = "admin" | "teacher" | "student" | "unknown";
type Session = { role: Role; email: string | null; emailVerified: boolean; withCode: boolean } | null;
const ROLES: Role[] = ["admin", "teacher", "student"];

export default function App() {
  const path = usePath();
  if (path === PATHS.home) return <Home />;
  if (path === PATHS.privacy) return <Privacy />;
  if (path === PATHS.signIn || path === PATHS.signUp || path === PATHS.app) return <SignedInArea path={path} />;
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
          const firebase = claims.firebase as { sign_in_second_factor?: string } | undefined;
          setSession({
            role,
            email: user.email,
            emailVerified: user.emailVerified,
            withCode: firebase?.sign_in_second_factor === "totp",
          });
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
  if (path === PATHS.signUp) return <SignUp signedIn={session !== null} />;
  if (path === PATHS.signIn || session === null) return <Login />;

  return (
    <div className="app">
      <AppHeader role={session.role} onSignOut={() => logOut()} />
      <SignedIn session={session} />
    </div>
  );
}

export function SignedIn({ session }: { session: NonNullable<Session> }) {
  const { role } = session;
  if (role === "unknown") return <Pending email={session.email} />;
  if ((role === "teacher" || role === "admin") && !session.withCode) {
    return <Setup email={session.email} emailVerified={session.emailVerified} />;
  }
  if (role === "admin") return <AdminApp />;
  if (role === "teacher") return <TeacherApp />;
  return <StudentApp />;
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
