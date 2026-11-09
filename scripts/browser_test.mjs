// The teacher's journey through the real pages, in headless Chrome:
// sign up, wait for approval, set up the authenticator from the on-screen
// key, sign in with the code. Complements scripts/live_test.py, which
// uses the REST API: this one runs the app's own sign-in code under the
// live security headers. The test login is deleted at the end.
//
//   node scripts/browser_test.mjs <app URL>
//
// Needs Google Chrome, Node 22+, and gcloud signed in as a project owner
// (for the approval step, scripts/browser_test_admin.py).
import { spawn, execFileSync } from "node:child_process";
import { createHmac } from "node:crypto";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
const HERE = dirname(fileURLToPath(import.meta.url));
const ADMIN_STEP = join(HERE, "browser_test_admin.py");
const PYTHON = join(HERE, "..", ".venv", "bin", "python");
const PROFILE = mkdtempSync(join(tmpdir(), "wb-browser-test-"));
const APP = process.argv[2].replace(/\/$/, ""), EMAIL = `browsertest${Date.now()}@example.com`, PASSWORD = "Journey-" + Math.random().toString(36).slice(2) + "x9";
const chrome = spawn("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", ["--headless=new", "--disable-gpu", "--no-first-run",
  "--remote-debugging-port=9334", `--user-data-dir=${PROFILE}`, "--window-size=1280,900", "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let targets; for (let i = 0; i < 40; i++) { try { targets = await (await fetch("http://127.0.0.1:9334/json")).json(); break; } catch { await sleep(250); } }
const ws = new WebSocket(targets.find((t) => t.type === "page").webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r));
let id = 0; const pending = new Map(); const problems = [];
ws.addEventListener("message", (ev) => { const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m.result); pending.delete(m.id); }
  if (m.method === "Runtime.exceptionThrown") problems.push("exception: " + (m.params.exceptionDetails.exception?.description ?? "").slice(0, 160));
  if (m.method === "Log.entryAdded" && m.params.entry.level === "error") problems.push("log: " + m.params.entry.text.slice(0, 160));
  if (m.method === "Network.loadingFailed" && m.params.blockedReason) problems.push("blocked: " + m.params.blockedReason);
  if (m.method === "Network.responseReceived" && m.params.response.status >= 400) problems.push(`http ${m.params.response.status}: ${m.params.response.url.split("?")[0].slice(0, 110)}`); });
const send = (method, params = {}) => new Promise((r) => { pending.set(++id, r); ws.send(JSON.stringify({ id, method, params })); });
for (const d of ["Runtime", "Log", "Network", "Page"]) await send(`${d}.enable`);
const run = async (js) => (await send("Runtime.evaluate", { expression: js, awaitPromise: true, returnByValue: true })).result.value;
const text = () => run("document.body.innerText");
const waitFor = async (needle, ms = 20000) => { for (let t = 0; t < ms; t += 400) { if ((await text()).includes(needle)) return true; await sleep(400); } return false; };
// React-friendly typing: the native value setter, then an input event.
const type = (selector, value) => run(`(() => { const el = document.querySelector(${JSON.stringify(selector)});
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(el, ${JSON.stringify(value)});
  el.dispatchEvent(new Event("input", { bubbles: true })); return true; })()`);
const click = (label) => run(`(() => { const b = [...document.querySelectorAll("button")].find((x) => x.innerText.trim() === ${JSON.stringify(label)}); b.click(); return !!b; })()`);
const totp = (secret) => { const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"; let bits = "";
  for (const c of secret.replace(/\s/g, "").toUpperCase()) bits += alphabet.indexOf(c).toString(2).padStart(5, "0");
  const key = Buffer.from(bits.match(/.{8}/g).map((b) => parseInt(b, 2))); const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 30000))); const h = createHmac("sha1", key).update(counter).digest();
  const o = h[h.length - 1] & 15; return String((h.readUInt32BE(o) & 0x7fffffff) % 1000000).padStart(6, "0"); };
const step = (name, ok) => { console.log(`${ok ? "PASS" : "FAIL"}  ${name}`); return ok; };
let ok = true;
try {
  await send("Page.navigate", { url: `${APP}/sign-up` });
  ok &&= step("sign-up page loads", await waitFor("Sign up as a teacher"));
  await type('input[autocomplete="name"]', "Journey Test"); await type('input[type="email"]', EMAIL); await type('input[type="password"]', PASSWORD);
  await click("Sign up");
  ok &&= step("sign-up leads to 'Waiting for approval'", await waitFor("Waiting for approval"));
  ok &&= step("the waiting page says the email isn't verified yet", (await text()).includes("Verify your email"));
  console.log("  " + execFileSync(PYTHON, [ADMIN_STEP, "approve", EMAIL]).toString().trim());
  await click("Check again");
  ok &&= step("after approval, 'Check again' opens the account setup", await waitFor("Set up an authenticator app"));
  await click("Start");
  ok &&= step("the QR code and key are shown", await waitFor("Can't scan it?") && await run("!!document.querySelector('svg.qr-code')"));
  const key = await run("document.querySelector('.setup-key')?.textContent ?? ''");
  await type('input[autocomplete="one-time-code"]', totp(key));
  await click("Finish setup");
  ok &&= step("finishing setup returns to sign-in with a confirmation", await waitFor("Your account is set up"));
  await sleep(31000 - (Date.now() % 30000));  // a fresh code window: codes can't be reused
  await type('input[type="email"]', EMAIL); await type('input[type="password"]', PASSWORD); await click("Next");
  ok &&= step("password step asks for the authenticator code", await waitFor("Enter the 6-digit") || await waitFor("6-digit code in your authenticator"));
  await type('input[autocomplete="one-time-code"]', totp(key)); await click("Verify and sign in");
  ok &&= step("signed in with the code: the teacher's first-run screen shows", await waitFor("Welcome to Write Better"));
  ok &&= step("no security-policy blocks or errors on the way", problems.length === 0);
  if (problems.length) console.log("  " + problems.join("\n  "));
} catch (err) {
  ok = false; console.log("ERROR", err.message);
} finally {
  console.log("  " + execFileSync(PYTHON, [ADMIN_STEP, "cleanup", EMAIL]).toString().trim());
  ws.close(); chrome.kill(); process.exit(ok ? 0 : 1);
}
