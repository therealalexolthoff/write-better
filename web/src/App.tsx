// Top level: waits for sign-in, then shows the teacher or student app
// based on the role claim the API set on the account.
import { useEffect, useState } from "react";
import { onIdTokenChanged } from "firebase/auth";
import { initAuth, logOut } from "./firebase";
import Login from "./Login";
import TeacherApp from "./teacher/TeacherApp";
import StudentApp from "./student/StudentApp";

type Role = "admin" | "teacher" | "student" | "unknown";
type Session = { role: Role } | null;
const ROLES: Role[] = ["admin", "teacher", "student"];

export default function App() {
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
      .catch(() => setError("Could not reach the server. Check your connection and reload."));
    return () => unsubscribe();
  }, []);

  if (error) return <main className="page"><p className="error">{error}</p></main>;
  if (session === undefined) return <main className="page"><p>Loading…</p></main>;
  if (session === null) return <Login />;

  return (
    <>
      <header className="topbar">
        <span>Write Better</span>
        <button className="link" onClick={() => logOut()}>Sign out</button>
      </header>
      {session.role === "teacher" && <TeacherApp />}
      {session.role === "student" && <StudentApp />}
      {session.role === "admin" && (
        <main className="page"><p className="notice">You're signed in as the admin. The admin screens are on their way.</p></main>
      )}
      {session.role === "unknown" && (
        <main className="page"><p className="error">This account isn't set up yet. Ask your teacher.</p></main>
      )}
    </>
  );
}
