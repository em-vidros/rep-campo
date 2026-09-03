/* REP Campo - service worker. Cache do app shell para funcionar offline. */
const CACHE = 'rep-campo-v3';
const SHELL = [
  '/static/app.js', '/static/styles.css', '/static/viagens.js',
  '/static/dicas.js', '/static/logo_em_vidros.svg', '/static/favicon.svg',
  '/static/icone-192.png', '/manifest.webmanifest',
];

self.addEventListener('install', ev => {
  ev.waitUntil(
    caches.open(CACHE).then(c =>
      // A pagina do app entra separada: ela e a unica que depende da sessao, e
      // um 302 para /login faria o addAll inteiro falhar.
      c.addAll(SHELL).then(() => c.add('/').catch(() => {}))
    ).then(() => self.skipWaiting())
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

  // Abrir o app: rede primeiro, copia guardada como reserva. Sem isto, quem
  // toca no icone da tela de inicio sem sinal ve a pagina de erro do navegador,
  // e a fila gravada no aparelho fica inalcancavel.
  if (req.mode === 'navigate') {
    ev.respondWith(
      fetch(req).then(resp => {
        if (resp.ok && resp.type === 'basic') {
          const copia = resp.clone();
          caches.open(CACHE).then(c => c.put(req, copia));
        }
        return resp;
      }).catch(() => caches.match(req).then(hit => hit || caches.match('/')))
    );
    return;
  }

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
