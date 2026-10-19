// Service worker: deixa o app instalável e abre mesmo com internet ruim.
// Estratégia "rede primeiro": sempre tenta a versão nova; se falhar, usa a guardada.
// Chamadas ao Supabase NÃO passam por aqui (são sempre ao vivo).
const CACHE = "caixa-emb-v6";
const ARQUIVOS = ["./", "index.html", "style.css", "app.js", "admin.js", "relatorios.js", "cadastros.js", "config.js", "manifest.json", "icons/logo.png", "icons/icon-192.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ARQUIVOS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== self.location.origin) return;
  e.respondWith(
    fetch(e.request)
      .then((resp) => {
        const copia = resp.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copia));
        return resp;
      })
      .catch(() => caches.match(e.request).then((r) => r || caches.match("index.html")))
  );
});
