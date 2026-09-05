/* REP Campo - service worker. Cache do app shell para funcionar offline. */
const CACHE = 'rep-campo-v9';
const SHELL = [
  '/static/app.js', '/static/styles.css', '/static/viagens.js',
  '/static/dicas.js', '/static/painel.css', '/static/logo_em_vidros.svg',
  '/static/favicon.svg', '/static/icone-192.png', '/manifest.webmanifest',
];

// GET de leitura que vale guardar. Sem rede, viagens mostra o roteiro da ultima
// vez que abriu com sinal em vez de nao mostrar nada. /api/resumo fica de fora
// de proposito: offline o app refaz a conta com as fichas do aparelho, e a conta
// nova vale mais que a copia velha do servidor.
const LEITURA = /^\/api\/(bootstrap|rotas|viagens|visitas-avulsas)(\/|$)/;

// So guarda pagina que veio inteira. Com a sessao vencida o servidor manda para
// /login, e guardar aquilo no lugar do app deixaria o REP olhando uma tela de
// senha sem rede, com a fila de fichas presa atras dela.
function guardarPagina(c, req) {
  return fetch(req, { redirect: 'follow' }).then(resp => {
    if (!resp.ok || resp.redirected || resp.type !== 'basic') return;
    return c.put(req, resp.clone());
  });
}

// Resposta tirada do cache vai marcada. O navegador mente sobre navigator.onLine
// numa pagina que ele mesmo abriu pelo cache: diz "online" sem rede nenhuma. O
// cabecalho e a unica prova honesta de que aquilo nao veio do servidor agora.
function marcada(resp) {
  if (!resp) return resp;
  const h = new Headers(resp.headers);
  h.set('X-Rep-Cache', '1');
  return resp.blob().then(corpo => new Response(corpo, {
    status: resp.status, statusText: resp.statusText, headers: h,
  }));
}

self.addEventListener('install', ev => {
  ev.waitUntil(
    caches.open(CACHE).then(c =>
      // As paginas entram separadas do addAll: elas dependem da sessao, e um
      // 302 para /login derrubaria o lote inteiro.
      c.addAll(SHELL).then(() => Promise.all(
        ['/', '/viagens'].map(u => guardarPagina(c, u).catch(() => {}))))
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
  if (url.pathname === '/ping') return;             // sonda de rede: nunca do cache

  // Abrir o app: rede primeiro, copia guardada como reserva. Sem isto, quem
  // toca no icone da tela de inicio sem sinal ve a pagina de erro do navegador,
  // e a fila gravada no aparelho fica inalcancavel.
  if (req.mode === 'navigate') {
    ev.respondWith(
      fetch(req).then(resp => {
        if (resp.ok && !resp.redirected && resp.type === 'basic') {
          const copia = resp.clone();
          caches.open(CACHE).then(c => c.put(req, copia));
        }
        return resp;
      }).catch(() => caches.match(req).then(hit => hit || caches.match('/')))
    );
    return;
  }

  // leitura: rede primeiro, cache como reserva (offline)
  if (LEITURA.test(url.pathname)) {
    ev.respondWith(
      fetch(req).then(resp => {
        // 401 de sessao vencida nao pode apagar a copia boa que ja esta guardada
        if (resp.ok) {
          const copia = resp.clone();
          caches.open(CACHE).then(c => c.put(req, copia));
        }
        return resp;
      }).catch(() => caches.match(req).then(marcada))
    );
    return;
  }
  if (url.pathname.startsWith('/api/')) return;      // o resto do /api exige rede

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
