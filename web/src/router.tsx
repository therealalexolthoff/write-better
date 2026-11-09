// The smallest router that works: the address bar's path picks the page,
// and links change it without reloading. No library needed. The API serves
// index.html for each page path (api/app/main.py), so reloads work too.
import { useEffect, useState, type MouseEvent, type ReactNode } from "react";

// Every page of the app. Keep in step with PAGES in api/app/main.py.
export const PATHS = { home: "/", privacy: "/privacy", signIn: "/sign-in", app: "/app" } as const;

const listeners = new Set<() => void>();

export function navigate(to: string, { replace = false } = {}) {
  if (to === window.location.pathname) return;
  if (replace) window.history.replaceState(null, "", to);
  else window.history.pushState(null, "", to);
  window.scrollTo(0, 0);
  listeners.forEach((listener) => listener());
}

export function usePath(): string {
  const [path, setPath] = useState(window.location.pathname);
  useEffect(() => {
    const update = () => setPath(window.location.pathname);
    listeners.add(update);
    window.addEventListener("popstate", update);
    return () => {
      listeners.delete(update);
      window.removeEventListener("popstate", update);
    };
  }, []);
  return path;
}

export function Link({ to, className, children }: { to: string; className?: string; children: ReactNode }) {
  function go(e: MouseEvent<HTMLAnchorElement>) {
    // Let the browser handle new-tab clicks (cmd/ctrl/shift/middle button).
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
    e.preventDefault();
    navigate(to);
  }
  return (
    <a href={to} className={className} onClick={go}>
      {children}
    </a>
  );
}
