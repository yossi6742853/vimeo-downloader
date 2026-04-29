// Service Worker for PWA — v7.3 (network-only, force update, kill cache)
const SW_VERSION = 'vg-v7.3-' + Date.now();
self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.map(k => caches.delete(k)));
    await self.clients.claim();
    // Force reload all open pages
    const clients = await self.clients.matchAll({type:'window'});
    clients.forEach(c => c.navigate(c.url));
})()));
self.addEventListener('fetch', e => {
    e.respondWith(fetch(e.request, { cache: 'no-store' }).catch(() => caches.match(e.request)));
});
