// Test tự động extension trong Chrome thật (Chrome for Testing, qua Puppeteer).
// Chạy: npm run build && npm run e2e      (thêm HEADFUL=1 để xem trình duyệt chạy)
//
// Không test được tự động: phân tích Gmail (cần đăng nhập) và nút quét QR
// (captureVisibleTab cần người dùng bấm vào icon extension).
import http from "node:http";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer";

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const DIST = join(ROOT, "dist");
const PORT = 5517;
const BASE = `http://127.0.0.1:${PORT}`; // địa chỉ IP: trang đăng nhập giả bị chấm nghi ngờ
const SAFE = `http://localhost:${PORT}`; // tên máy thường: trang sạch không bị chấm

// Trang thử được phục vụ từ thư mục test/ + vài trang sinh tại chỗ.
const PAGES = {
  "/hover.html": `<!doctype html><meta charset="utf-8"><body style="padding:40px">
    <a id="bad" href="https://secure-vietcombank-xacminh.top/login">Đăng nhập ngân hàng</a><br><br>
    <a id="good" href="https://vnexpress.net/">Đọc báo</a></body>`,
  "/clean.html": `<!doctype html><meta charset="utf-8"><title>Trang thường</title><body><p>Xin chào</p></body>`,
  // Kiểu web phim lậu, nhưng mạng quảng cáo KHÔNG có trong danh sách (trang mở ở localhost, trang đích ở "web" khác: 127.0.0.1;
  // không đặt trang nguồn ở 127.0.0.1 vì banner "đáng ngờ" (địa chỉ IP) sẽ che nút).
  "/popunder.html": `<!doctype html><meta charset="utf-8"><body style="padding:20px">
    <button id="play">▶ Xem phim</button>
    <button id="blank">▶ Tập 2</button>
    <button id="login">Đăng nhập (cửa sổ nhỏ)</button>
    <a id="real" href="${BASE}/clean.html?link" target="_blank">Link thật sang web khác</a>
    <script>
      const AD = "${BASE}/clean.html?utm_source=lạ";
      play.onclick = () => window.open(AD, "_blank");
      blank.onclick = () => { const w = window.open("", "_blank"); w.location = AD + "&blank"; };
      login.onclick = () => window.open("${BASE}/clean.html?login", "_blank", "width=480,height=600");
    </script></body>`,
  "/overlay.html": `<!doctype html><meta charset="utf-8"><body><p>Nội dung phim…</p>
    <a id="ov" href="${BASE}/clean.html?overlay" target="_blank"
       style="position:fixed;inset:0;opacity:0;z-index:9999"></a></body>`,
};
const server = http.createServer((req, res) => {
  const path = req.url.split("?")[0];
  try {
    const body = PAGES[path] ?? readFileSync(join(ROOT, "test", path.replace(/^\/+/, "")));
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    res.end(body);
  } catch {
    res.writeHead(404);
    res.end("not found");
  }
});
await new Promise((r) => server.listen(PORT, "127.0.0.1", r));

const browser = await puppeteer.launch({
  headless: !process.env.HEADFUL,
  args: [`--disable-extensions-except=${DIST}`, `--load-extension=${DIST}`, "--no-first-run"],
});

const results = [];
async function test(name, fn) {
  const t = Date.now();
  try {
    const info = await fn();
    results.push(true);
    console.log(`✅ ${name.padEnd(52)} ${String(Date.now() - t).padStart(5)} ms  ${info ?? ""}`);
  } catch (e) {
    results.push(false);
    console.log(`❌ ${name.padEnd(52)} ${String(Date.now() - t).padStart(5)} ms  ${e.message.split("\n")[0]}`);
  }
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function waitFor(fn, timeout = 15000, step = 200) {
  const end = Date.now() + timeout;
  while (Date.now() < end) {
    const v = await fn();
    if (v) return v;
    await sleep(step);
  }
  throw new Error(`hết ${timeout} ms mà chưa thấy kết quả`);
}

// ---------- Tìm extension và chờ luật chặn quảng cáo được cài ----------
const worker = await (await browser.waitForTarget((t) => t.type() === "service_worker" && t.url().endsWith("background.js"))).worker();
const extId = new URL(worker.url()).host;
const rulesInstalled = () => worker.evaluate(async () => (await chrome.declarativeNetRequest.getDynamicRules()).length);

await test("Extension nạp được, luật chặn quảng cáo đã cài", async () => {
  const n = await waitFor(rulesInstalled);
  return `id ${extId}, ${n} luật`;
});

const page = await browser.newPage();

await test("Trang đăng nhập giả → banner cảnh báo", async () => {
  await page.goto(`${BASE}/fake-login.html`);
  const text = await waitFor(() => page.evaluate(() =>
    document.getElementById("phishguard-banner-host")?.shadowRoot?.querySelector(".bar")?.textContent), 30000);
  if (!/phishing|lừa đảo|đáng ngờ/i.test(text)) throw new Error("banner không có nội dung cảnh báo");
  return text.slice(0, 60).replace(/\s+/g, " ");
});

await test("Kết quả được lưu kèm URL (popup so với tab hiện tại)", async () => {
  // Extension không có quyền "tabs" nên không đọc được URL tab ở đây (popup thật thì có,
  // nhờ activeTab khi người dùng bấm icon) → tìm trong bộ nhớ phiên theo URL.
  const all = await worker.evaluate(() => chrome.storage.session.get(null));
  const stored = Object.values(all).find((r) => r?.url === `${BASE}/fake-login.html`);
  if (!stored) throw new Error(`không thấy kết quả lưu kèm URL: ${JSON.stringify(all).slice(0, 200)}`);
  return `${stored.verdict} ${stored.score} (${stored.source}), ${stored.breakdown?.length ?? 0} tín hiệu`;
});

await test("Trang bình thường → không có banner", async () => {
  await page.goto(`${SAFE}/clean.html`);
  await sleep(4000);
  const has = await page.evaluate(() => !!document.getElementById("phishguard-banner-host"));
  if (has) throw new Error("trang thường mà vẫn hiện banner");
  return "không có banner";
});

await test("Rê chuột vào link giả → tooltip cảnh báo", async () => {
  await page.goto(`${SAFE}/hover.html`);
  await page.hover("#bad");
  const text = await waitFor(() => page.evaluate(() =>
    document.getElementById("phishguard-link-tip")?.shadowRoot?.querySelector(".tip")?.textContent), 5000);
  return text.slice(0, 70);
});

await test("Rê chuột vào link thật → không có tooltip", async () => {
  await page.mouse.move(0, 0);
  await sleep(300);
  await page.hover("#good");
  await sleep(1200);
  const has = await page.evaluate(() => !!document.getElementById("phishguard-link-tip"));
  if (has) throw new Error("link thật mà vẫn hiện tooltip");
  return "không có tooltip";
});

await test("Chuyển hướng tới mạng quảng cáo → trang cảnh báo", async () => {
  await page.goto("https://popads.net/").catch(() => {});
  await waitFor(() => page.url().includes("blocked.html"), 10000);
  const title = await page.$eval("#title", (e) => e.textContent);
  return `${new URL(page.url()).hash.slice(0, 30)}…  "${title.trim().slice(0, 40)}"`;
});

await test("Trang cảnh báo hiện đúng URL bị chặn", async () => {
  const shown = await page.$eval("#url", (e) => e.textContent);
  if (!shown.startsWith("https://popads.net")) throw new Error(`hiện sai: ${shown}`);
  return shown;
});

await test("Bấm 'Mở lần này' → được đi tiếp", async () => {
  await page.click("#go");
  await waitFor(() => /^https:\/\/(www\.)?popads\.net/.test(page.url()), 15000);
  return page.url();
});

await test("Popunder mở link affiliate Shopee → cảnh báo affiliate", async () => {
  await page.goto(`${BASE}/ad-redirect.html`);
  const popup = new Promise((r) => browser.once("targetcreated", r));
  await page.click("#affiliate");
  const target = await popup;
  await waitFor(() => target.url().includes("blocked.html"), 10000);
  const p = await target.page();
  // Chờ blocked.js chạy xong (đã điền URL) rồi mới đọc tiêu đề, vì HTML gốc mặc định là "quảng cáo".
  await waitFor(() => p.$eval("#url", (e) => e.textContent.startsWith("http")).catch(() => false));
  const title = await p.$eval("#title", (e) => e.textContent);
  await p.close();
  if (!/affiliate|tiếp thị/i.test(title)) throw new Error(`tiêu đề sai: ${title}`);
  return title.trim();
});

// ---------- Popunder của mạng quảng cáo lạ (không có trong danh sách) ----------
// Tab mới xuất hiện SAU cú bấm (không dùng sự kiện targetcreated: dễ bắt nhầm tab khác).
async function clickOpensTab(p, click) {
  const before = new Set(browser.targets());
  await click();
  return browser.waitForTarget((t) => t.type() === "page" && !before.has(t), { timeout: 8000 });
}
// Đóng mọi tab trừ tab chính. (Không dùng target.page(): Puppeteer treo với tab mở bằng window.open("").)
async function closeOtherTabs() {
  for (const p of await browser.pages()) if (p !== page) await p.close().catch(() => {});
  await page.bringToFront(); // tab nền không được vẽ lại → page.click() chờ mãi
}
async function expectBlocked(target) {
  try {
    await waitFor(() => target.url().includes("blocked.html#pop"), 8000);
    return decodeURIComponent(target.url().split("#pop|")[1] ?? "");
  } finally {
    await closeOtherTabs();
  }
}
async function expectNotBlocked(target) {
  await sleep(2500);
  const url = target.url();
  await closeOtherTabs();
  if (url.includes("blocked.html")) throw new Error(`bị chặn nhầm: ${url}`);
  return url;
}

await test("Bấm nút Play, trang tự mở tab sang web lạ → chặn", async () => {
  await page.goto(`${SAFE}/popunder.html`);
  const target = await clickOpensTab(page, () => page.click("#play"));
  await waitFor(() => target.url().includes("blocked.html#pop"), 8000);
  const p = await target.page();
  await waitFor(() => p.$eval("#title", (e) => /tự bật/.test(e.textContent)).catch(() => false), 5000);
  const title = await p.$eval("#title", (e) => e.textContent.trim());
  return `${title} — ${await expectBlocked(target)}`;
});

await test("Tab mở trống rồi mới gán địa chỉ quảng cáo → chặn", async () => {
  return expectBlocked(await clickOpensTab(page, () => page.click("#blank")));
});

await test("Bấm trúng link trong suốt phủ kín trang → chặn", async () => {
  await page.goto(`${SAFE}/overlay.html`);
  return expectBlocked(await clickOpensTab(page, () => page.mouse.click(300, 200)));
});

await test("Bấm link thật mở tab sang web khác → không chặn", async () => {
  await page.goto(`${SAFE}/popunder.html`);
  return expectNotBlocked(await clickOpensTab(page, () => page.click("#real")));
});

await test("Cửa sổ đăng nhập (window.open có kích thước) → không chặn", async () => {
  return expectNotBlocked(await clickOpensTab(page, () => page.click("#login")));
});

await test("URL tự khai utm_medium=popunder (như yo88) → chặn", async () => {
  await page.goto(`${SAFE}/clean.html?a=1&utm_source=nanaproorg&utm_medium=popunder&utm_campaign=cpd`).catch(() => {});
  await waitFor(() => page.url().includes("blocked.html#pop"), 8000);
  return decodeURIComponent(new URL(page.url()).hash).slice(0, 60);
});

await test("Link thường (vnexpress) không bị chặn", async () => {
  await page.goto("https://vnexpress.net/", { waitUntil: "domcontentloaded" }).catch(() => {});
  await sleep(500);
  if (page.url().includes("blocked.html")) throw new Error("bị chặn nhầm");
  return new URL(page.url()).host;
});

await test("Tắt công tắc chặn quảng cáo → không chặn nữa", async () => {
  await worker.evaluate(() => chrome.storage.local.set({ adBlock: false }));
  await waitFor(async () => (await rulesInstalled()) === 0, 5000);
  await page.goto("https://popads.net/", { waitUntil: "domcontentloaded" }).catch(() => {});
  await sleep(500);
  const blocked = page.url().includes("blocked.html");
  await worker.evaluate(() => chrome.storage.local.set({ adBlock: true }));
  await waitFor(rulesInstalled, 5000);
  if (blocked) throw new Error("vẫn bị chặn khi đã tắt");
  return "không chặn khi tắt, bật lại thì luật được cài lại";
});

await test("Popup mở được, đủ các phần", async () => {
  const p = await browser.newPage();
  await p.goto(`chrome-extension://${extId}/popup.html`);
  await sleep(800);
  const info = await p.evaluate(() => ({
    adToggle: document.getElementById("ad-block")?.checked,
    gmailToggle: document.getElementById("gmail-scan")?.checked,
    qrBtn: !!document.getElementById("scan-qr"),
    history: document.getElementById("history-count")?.textContent,
    adCount: document.getElementById("ad-count")?.textContent,
  }));
  await p.close();
  if (!info.adToggle || !info.gmailToggle || !info.qrBtn) throw new Error(JSON.stringify(info));
  return `lịch sử ${info.history} dòng; ${info.adCount}`;
});

await browser.close();
server.close();
const passed = results.filter(Boolean).length;
console.log(`\n${passed}/${results.length} đạt.`);
process.exit(passed === results.length ? 0 : 1);
