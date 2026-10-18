// Service worker tối giản để trang kiểm tra cài được như ứng dụng trên điện thoại (PWA).
// Chỉ lưu sẵn giao diện; mọi lời gọi kiểm tra (POST) luôn đi thẳng tới máy chủ.
const CACHE = "phishguard-shell-v1";
const SHELL = ["/", "/static/style.css", "/static/check.js", "/static/icon-192.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

// Ưu tiên mạng (luôn có bản mới nhất), mất mạng thì dùng bản đã lưu.
self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== location.origin || !SHELL.includes(url.pathname)) return;
  event.respondWith(
    fetch(req)
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy));
        return res;
      })
      .catch(() => caches.match(req)),
  );
});
