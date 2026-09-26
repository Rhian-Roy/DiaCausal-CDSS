/* Offline support: after the first visit, DiaCausal opens and works without internet.
   The cache name changes whenever the site changes, so a new version replaces the old.
   Only this website's own files are cached; sign-in requests to the account service are never cached.
   config.json (made at deploy time, not in git) is cached the first time it loads. */
const VERSION = "diacausal-v2";
const ASSETS = [
  "./",
  "./index.html",
  "./styles.css",
  "./app.js",
  "./engine.js",
  "./evidence.js",
  "./evidence.json",
  "./auth.js",
  "./account.js",
  "./model.json",
  "./results.json",
  "./manifest.webmanifest",
  "./vendor/marked.min.js",
  "./vendor/supabase.min.js",
  "./icons/icon.svg",
  "./icons/apple-touch-icon.png",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./icons/qr.png",
  "./docs/causal-engine.md",
  "./docs/results-summary.md",
  "./results/overlap.png",
  "./results/love_plot.png",
  "./results/ate_vs_truth.png",
  "./results/cate_recovery.png",
  "./results/calibration.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(VERSION).then((c) => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

// Network first (so updates show at once), falling back to the cache when offline.
self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET" || new URL(event.request.url).origin !== location.origin) return;
  event.respondWith(
    fetch(event.request)
      .then((resp) => {
        const copy = resp.clone();
        caches.open(VERSION).then((c) => c.put(event.request, copy));
        return resp;
      })
      .catch(() => caches.match(event.request).then((hit) => hit || caches.match("./index.html"))),
  );
});
