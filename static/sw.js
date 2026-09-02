/* REP Campo - service worker. Cache do app shell para funcionar offline. */
const CACHE = 'rep-campo-v2';
const SHELL = [
  '/static/app.js', '/static/styles.css', '/static/viagens.js',
  '/manifest.webmanifest',
];

self.addEventListener('install', ev => {
  ev.waitUntil(
    caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', ev => {
  ev.waitUntil(
    caches.keys().then(nomes =>
      Promise.all(nomes.filter(n => n !== CACHE).map(n => caches.delete(n)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', ev => {
  const req = ev.request;
  if (req.method !== 'GET') return;                 // POST de ficha nunca e cacheado
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/foto/')) return;

  // /api/bootstrap: rede primeiro, cache como reserva (offline)
  if (url.pathname === '/api/bootstrap') {
    ev.respondWith(
      fetch(req).then(resp => {
        const copia = resp.clone();
        caches.open(CACHE).then(c => c.put(req, copia));
        return resp;
      }).catch(() => caches.match(req))
    );
    return;
  }
  if (url.pathname.startsWith('/api/')) return;      // resumo/listagem exigem rede

  // app shell: cache primeiro
  ev.respondWith(
    caches.match(req).then(hit => hit || fetch(req).then(resp => {
      if (resp.ok && resp.type === 'basic') {
        const copia = resp.clone();
        caches.open(CACHE).then(c => c.put(req, copia));
      }
      return resp;
    }).catch(() => caches.match('/')))
  );
});
