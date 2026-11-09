// Sign-in through Identity Platform via the Firebase SDK. The browser
// config comes from the API's GET /config, so nothing is baked into the build.
import { initializeApp } from "firebase/app";
import {
  createUserWithEmailAndPassword,
  getAuth,
  getMultiFactorResolver,
  multiFactor,
  reload,
  sendEmailVerification,
  signInWithEmailAndPassword,
  signOut,
  TotpMultiFactorGenerator,
  updateProfile,
  type Auth,
  type MultiFactorError,
  type MultiFactorResolver,
  type TotpSecret,
  type User,
} from "firebase/auth";

// Must match STUDENT_EMAIL_DOMAIN in api/app/identity.py.
const STUDENT_EMAIL_DOMAIN = "students.internal";

let auth: Auth | null = null;

export async function initAuth(): Promise<Auth> {
  if (!auth) {
    const config = await (await fetch("/config")).json();
    auth = getAuth(initializeApp(config.firebase));
  }
  return auth;
}

export function currentAuth(): Auth {
  if (!auth) throw new Error("auth not initialised");
  return auth;
}

export async function studentSignIn(username: string, password: string): Promise<void> {
  await signInWithEmailAndPassword(currentAuth(), `${username.trim()}@${STUDENT_EMAIL_DOMAIN}`, password);
}

// Step 1 of teacher sign-in. Returns the resolver for step 2 (the
// authenticator code). The teacher account always has TOTP enrolled, so
// a password-only success should never happen; if it does, the API
// refuses the token anyway (api/app/auth.py).
export async function teacherPasswordStep(email: string, password: string): Promise<MultiFactorResolver | null> {
  try {
    await signInWithEmailAndPassword(currentAuth(), email, password);
    return null;
  } catch (err) {
    if ((err as { code?: string }).code === "auth/multi-factor-auth-required") {
      return getMultiFactorResolver(currentAuth(), err as MultiFactorError);
    }
    throw err;
  }
}

export async function teacherCodeStep(resolver: MultiFactorResolver, code: string): Promise<void> {
  const hint = resolver.hints.find((h) => h.factorId === TotpMultiFactorGenerator.FACTOR_ID);
  if (!hint) throw new Error("No authenticator app is set up for this account.");
  const assertion = TotpMultiFactorGenerator.assertionForSignIn(hint.uid, code.trim());
  await resolver.resolveSignIn(assertion);
}

export function logOut(): Promise<void> {
  return signOut(currentAuth());
}

function signedInUser(): User {
  const user = currentAuth().currentUser;
  if (!user) throw new Error("You're signed out. Sign in again to continue.");
  return user;
}

// ---- teacher sign-up and first sign-in ----

// Creates the teacher's login in Identity Platform (the password goes only
// there, never to our API) and sends the verification email. The new login
// has no role until the admin approves it.
export async function teacherSignUp(name: string, email: string, password: string): Promise<void> {
  const { user } = await createUserWithEmailAndPassword(currentAuth(), email.trim(), password);
  await updateProfile(user, { displayName: name.trim() });
  await sendEmailVerification(user, BACK_TO_APP);
}

// The verification page Google hosts offers a button back to the app.
const BACK_TO_APP = { url: `${window.location.origin}/app` };

export async function resendVerificationEmail(): Promise<void> {
  await sendEmailVerification(signedInUser(), BACK_TO_APP);
}

// Reloads the account and gets a fresh token, so a newly verified email or
// a role the admin just granted shows up straight away.
export async function refreshAccount(): Promise<void> {
  const user = signedInUser();
  await reload(user);
  await user.getIdToken(true);
}

export type AuthenticatorSetup = { secret: TotpSecret; key: string; url: string };

// Step 1 of adding an authenticator app: a new secret, shown to the user as
// a key to type in (or a link that opens the app on a phone).
export async function startAuthenticatorSetup(): Promise<AuthenticatorSetup> {
  const user = signedInUser();
  const session = await multiFactor(user).getSession();
  const secret = await TotpMultiFactorGenerator.generateSecret(session);
  return { secret, key: secret.secretKey, url: secret.generateQrCodeUrl(user.email ?? "Write Better", "Write Better") };
}

// Step 2: the first code from the app proves it's set up, and enrolls it.
export async function finishAuthenticatorSetup(setup: AuthenticatorSetup, code: string): Promise<void> {
  const assertion = TotpMultiFactorGenerator.assertionForEnrollment(setup.secret, code.trim());
  await multiFactor(signedInUser()).enroll(assertion, "Authenticator app");
}

// Identity Platform error codes, in words a person can act on.
export function authErrorMessage(err: unknown): string {
  const code = (err as { code?: string }).code ?? "";
  const messages: Record<string, string> = {
    "auth/email-already-in-use": "That email can't be used. If you've already signed up, sign in instead.",
    "auth/invalid-email": "That doesn't look like an email address.",
    "auth/weak-password": "Choose a longer password: at least 12 characters.",
    "auth/invalid-verification-code": "That code didn't work. Try the code your app shows now.",
    "auth/requires-recent-login": "For your security, sign in again, then continue the setup.",
    "auth/unverified-email": "Verify your email first, then set up the authenticator.",
    "auth/too-many-requests": "Too many attempts. Wait a few minutes and try again.",
    "auth/network-request-failed": "No connection. Check your internet and try again.",
  };
  return messages[code] ?? (err as Error).message ?? "Something went wrong. Please try again.";
}
