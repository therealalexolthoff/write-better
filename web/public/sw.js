// Write Better service worker: makes the site installable as a phone app and
// shows an offline page when a page can't load.
//
// Privacy: this worker only ever stores the offline page and its icon. It
// never caches pages, API responses, student writing or photos; everything
// else goes straight to the network as if the worker weren't there.
// Change CACHE's version when offline.html or the icon changes.
const CACHE = "write-better-offline-v1";
const OFFLINE_FILES = ["/offline.html", "/icons/icon-192.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(OFFLINE_FILES)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  // Remove offline caches from older versions of this worker.
  event.waitUntil(
    caches.keys().then((names) => Promise.all(names.filter((n) => n !== CACHE).map((n) => caches.delete(n)))),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.mode === "navigate") {
    // Opening a page: try the network; if it fails, show the offline page.
    event.respondWith(fetch(request).catch(() => caches.match("/offline.html")));
  } else if (OFFLINE_FILES.includes(new URL(request.url).pathname)) {
    // The offline page's own icon, which must load while offline.
    event.respondWith(caches.match(request).then((hit) => hit || fetch(request)));
  }
  // Anything else: not handled here, so the browser fetches it normally.
});
