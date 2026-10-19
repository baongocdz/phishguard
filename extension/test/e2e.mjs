// Test tự động extension trong Chrome thật (Chrome for Testing, qua Puppeteer).
// Chạy: npm run build && npm run e2e      (thêm HEADFUL=1 để xem trình duyệt chạy)
//
// Gmail được test bằng trang giả lập cấu trúc DOM Gmail tại mail.google.com (chặn request, trả HTML giả).
// Nút quét QR: chụp màn hình cần quyền activeTab (có khi người dùng bấm icon, Puppeteer không bấm được) → test chạy
// trên BẢN SAO dist-e2e/ có thêm quyền <all_urls>; bản phát hành (dist/) giữ nguyên quyền.
import http from "node:http";
import { cpSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer";

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const DIST = join(ROOT, "dist-e2e");
rmSync(DIST, { recursive: true, force: true });
cpSync(join(ROOT, "dist"), DIST, { recursive: true });
const testManifest = JSON.parse(readFileSync(join(DIST, "manifest.json"), "utf8"));
testManifest.host_permissions.push("<all_urls>");
writeFileSync(join(DIST, "manifest.json"), JSON.stringify(testManifest, null, 2));
// E2E_API=http://localhost:8000: bản test gọi backend ở máy thay vì Render (chạy backend đó với Gemini tắt để
// không tốn hạn mức Gemini — gói Free có model chỉ 20 lượt/ngày; test cũng nhanh và ổn định hơn).
if (process.env.E2E_API) {
  for (const f of readdirSync(DIST).filter((n) => n.endsWith(".js"))) {
    const file = join(DIST, f);
    writeFileSync(file, readFileSync(file, "utf8").replaceAll("https://phishguard-backend-g3w0.onrender.com", process.env.E2E_API));
  }
  console.log(`(backend: ${process.env.E2E_API})`);
}
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
    <button id="popwin">▶ Tập 3 (quảng cáo cửa sổ nhỏ)</button>
    <button id="tabunder">▶ Tập 4 (phim mở tab mới, tab này thành quảng cáo)</button>
    <a id="real" href="${BASE}/clean.html?link" target="_blank">Link thật sang web khác</a>
    <a id="real-same" href="${BASE}/clean.html?samelink">Link thật, mở ngay tab này</a>
    <form id="f" action="${BASE}/clean.html" method="get"><input name="q" value="x"><button id="send">Gửi</button></form>
    <script>
      const AD = "${BASE}/clean.html?utm_source=lạ";
      play.onclick = () => window.open(AD, "_blank");
      blank.onclick = () => { const w = window.open("", "_blank"); w.location = AD + "&blank"; };
      login.onclick = () => window.open("${BASE}/oauth/authorize?client_id=abc", "_blank", "width=480,height=600");
      popwin.onclick = () => window.open(AD + "&win", "", "width=400,height=300");
      tabunder.onclick = () => { window.open(location.href + "#xem-phim", "_blank"); location.href = AD + "&tabunder"; };
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
const isSw = (t) => t.type() === "service_worker" && t.url().endsWith("background.js");
const worker = await (await browser.waitForTarget(isSw)).worker();
const extId = new URL(worker.url()).host;
// Service worker vừa khởi động có thể chưa có API chrome.* → coi như 0 rồi thử lại.
const rulesInstalled = () => worker.evaluate(async () => (await chrome.declarativeNetRequest?.getDynamicRules())?.length ?? 0)
  .catch(() => 0);

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

await test("Quảng cáo mở bằng cửa sổ nhỏ (popunder cổ điển) → chặn", async () => {
  await page.goto(`${SAFE}/popunder.html`);
  return expectBlocked(await clickOpensTab(page, () => page.click("#popwin")));
});

await test("Tab-under: bấm Play, chính tab này bị đổi sang web lạ → cảnh báo", async () => {
  await page.goto(`${SAFE}/popunder.html`);
  await page.click("#tabunder");
  await waitFor(() => page.url().includes("blocked.html#tu"), 8000);
  await closeOtherTabs();
  return decodeURIComponent(page.url().split("#tu|")[1] ?? "");
});

await test("Bấm link thật mở ngay tab này sang web khác → không chặn", async () => {
  await page.goto(`${SAFE}/popunder.html`);
  await Promise.all([page.waitForNavigation({ waitUntil: "domcontentloaded" }).catch(() => {}), page.click("#real-same")]);
  await sleep(800);
  if (page.url().includes("blocked.html")) throw new Error(`bị chặn nhầm: ${page.url()}`);
  return page.url();
});

await test("Bấm link xong bấm Back ngay → không bị coi là quảng cáo", async () => {
  await page.goBack({ waitUntil: "domcontentloaded" }).catch(() => {});
  await sleep(800);
  if (page.url().includes("blocked.html")) throw new Error(`bị chặn nhầm: ${page.url()}`);
  return page.url();
});

await test("Gửi form sang web khác → không chặn", async () => {
  await page.goto(`${SAFE}/popunder.html`);
  await Promise.all([page.waitForNavigation({ waitUntil: "domcontentloaded" }).catch(() => {}), page.click("#send")]);
  await sleep(800);
  if (page.url().includes("blocked.html")) throw new Error(`bị chặn nhầm: ${page.url()}`);
  return page.url();
});

await test("URL tự khai utm_medium=popunder (như yo88) → chặn", async () => {
  await page.goto(`${SAFE}/clean.html?a=1&utm_source=nanaproorg&utm_medium=popunder&utm_campaign=cpd`).catch(() => {});
  await waitFor(() => page.url().includes("blocked.html#mk"), 8000);
  return decodeURIComponent(new URL(page.url()).hash).slice(0, 60);
});

await test("Bấm banner quảng cáo utm_medium=banner_popup_400x400 (như net88) → cảnh báo", async () => {
  await page.goto(`${SAFE}/clean.html?a=0a4d&utm_campaign=cpd&utm_source=phim_x&utm_medium=banner_popup_400x400`).catch(() => {});
  await waitFor(() => page.url().includes("blocked.html#mk"), 8000);
  await waitFor(() => page.$eval("#title", (e) => /quảng cáo bật lên/.test(e.textContent)).catch(() => false), 5000);
  return page.$eval("#title", (e) => e.textContent.trim());
});

await test("utm_medium bình thường (popular, email) → không chặn", async () => {
  await page.goto(`${SAFE}/clean.html?utm_medium=popular&utm_source=newsletter`).catch(() => {});
  await sleep(800);
  if (page.url().includes("blocked.html")) throw new Error("bị chặn nhầm");
  return new URL(page.url()).search;
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

// ---------- Gmail giả lập: trả HTML có cấu trúc giống Gmail ngay tại mail.google.com để gmail.js chạy ----------
function thread(subject, senderName, senderEmail, body, linkText, href) {
  return `<div class="ha"><h2 class="hP">${subject}</h2></div>
    <div class="gs"><span class="gD" email="${senderEmail}" name="${senderName}">${senderName}</span>
      <div class="a3s">${body} <a href="${href}">${linkText}</a></div></div>`;
}
function fakeGmail(...args) {
  return `<!doctype html><meta charset="utf-8"><body><div style="height:40px">Gmail</div>${thread(...args)}</body>`;
}
const SPOOF_VCB = ["[KHẨN] Tài khoản sẽ bị tạm khóa trong 24 giờ", "Vietcombank", "thongbao@vcb-canhbao.com",
  "Kính gửi quý khách, vui lòng nhập mật khẩu và mã OTP để xác minh.",
  "https://www.vietcombank.com.vn/xac-minh", "https://vcb-xacminh-taikhoan.top/login"];
const REAL_GOOGLE = ["Cảnh báo bảo mật", "Google", "no-reply@accounts.google.com",
  "Chúng tôi phát hiện thấy có một yêu cầu đăng nhập mới vào Tài khoản Google của bạn trên một thiết bị Windows. "
    + "Nếu đây không phải là yêu cầu của bạn, thì chúng tôi sẽ giúp bạn bảo mật tài khoản.",
  "Kiểm tra hoạt động", "https://accounts.google.com/AccountChooser?Email=a.b@gmail.com&continue=x"];
// Giống Gmail thật: ứng dụng một trang đổi DOM liên tục (đồng hồ), mở thư bằng #inbox/<id>, thư đã xem chỉ bị ẩn.
const GMAIL_SPA = `<!doctype html><meta charset="utf-8"><body><div id="clock"></div>
  <div id="list">Hộp thư đến</div>
  <div id="T1" class="thread">${thread(...SPOOF_VCB)}</div>
  <div id="T2" class="thread">${thread(...REAL_GOOGLE)}</div>
  <script>
    setInterval(() => { clock.textContent = Date.now(); }, 100);
    function route() {
      const id = location.hash.split("/")[1];
      document.querySelectorAll(".thread").forEach((t) => { t.style.display = t.id === id ? "" : "none"; });
      list.style.display = id ? "none" : "";
    }
    addEventListener("hashchange", route); route();
  </script></body>`;
async function openFakeGmail(threadId, html) {
  const p = await browser.newPage();
  await p.setRequestInterception(true);
  p.on("request", (r) => (r.url().startsWith("https://mail.google.com/")
    ? r.respond({ status: 200, contentType: "text/html; charset=utf-8", body: html })
    : r.continue()));
  await p.goto(`https://mail.google.com/mail/u/0/#inbox/${threadId}`);
  const box = await waitFor(() => p.evaluate(() => {
    const b = document.querySelector(".phishguard-email-banner")?.shadowRoot?.querySelector(".box");
    return b && !b.classList.contains("loading") ? { cls: b.className, text: b.textContent } : null;
  }), 40000);
  const underSubject = await p.evaluate(() =>
    document.querySelector("h2.hP").parentElement.nextElementSibling?.className === "phishguard-email-banner");
  const all = await worker.evaluate(() => chrome.storage.session.get(null));
  const stored = Object.entries(all).find(([k, v]) => k.startsWith("email:") && v.url?.endsWith(threadId))?.[1];
  await p.close();
  return { box, underSubject, stored };
}

await test("Gmail: email giả ngân hàng → thanh đỏ dưới tiêu đề, popup có kết quả", async () => {
  const { box, underSubject, stored } = await openFakeGmail("FAKEVCB1", fakeGmail(...SPOOF_VCB));
  if (!/phishing|suspicious/.test(box.cls)) throw new Error(`thanh sai: ${box.cls} ${box.text.slice(0, 60)}`);
  if (!underSubject) throw new Error("thanh không nằm dưới tiêu đề");
  if (!stored) throw new Error("popup không có kết quả email");
  return `${stored.result.verdict} ${stored.result.score}; ${box.text.slice(0, 50)}`;
});

await test("Gmail: thư bảo mật thật của Google → thanh xanh 'đã kiểm tra'", async () => {
  const { box, stored } = await openFakeGmail("FAKEGOOG1", fakeGmail(...REAL_GOOGLE));
  if (!box.cls.includes("safe")) throw new Error(`thanh sai: ${box.cls} ${box.text.slice(0, 80)}`);
  return `${stored?.result.verdict}; ${box.text.slice(0, 50)}`;
});

await test("Gmail: mở thư 1, quay ra, mở thư 2 (không F5) → thư 2 cũng được kiểm tra", async () => {
  const p = await browser.newPage();
  await p.setRequestInterception(true);
  p.on("request", (r) => (r.url().startsWith("https://mail.google.com/")
    ? r.respond({ status: 200, contentType: "text/html; charset=utf-8", body: GMAIL_SPA })
    : r.continue()));
  await p.goto("https://mail.google.com/mail/u/0/#inbox");
  // Thanh đang HIỂN THỊ (Gmail giữ thư cũ ở dạng ẩn).
  const shown = () => p.evaluate(() => {
    const host = [...document.querySelectorAll(".phishguard-email-banner")].find((h) => h.getClientRects().length);
    const b = host?.shadowRoot?.querySelector(".box");
    return b && !b.classList.contains("loading") ? b.className : null;
  });
  const state = () => p.evaluate(() => [...document.querySelectorAll(".phishguard-email-banner")].map((h) =>
    `${h.closest(".thread")?.id}:${h.getClientRects().length ? "hiện" : "ẩn"}:${h.shadowRoot?.querySelector(".box")?.className}`).join(", "));
  let stage = "thư 1";
  try {
    await p.evaluate(() => { location.hash = "#inbox/T1"; });
    const first = await waitFor(shown, 30000);
    await p.evaluate(() => { location.hash = "#inbox"; });
    await sleep(1000);
    stage = "thư 2";
    await p.evaluate(() => { location.hash = "#inbox/T2"; });
    const second = await waitFor(async () => { const c = await shown(); return c?.includes("safe") ? c : null; }, 30000);
    return `thư 1: ${first}; thư 2: ${second}`;
  } catch (e) {
    throw new Error(`${stage}: ${e.message}; các thanh: ${await state()}`);
  } finally {
    await p.close();
  }
});

await test("Popup: nút 'Quét mã QR trên màn hình' đọc được mã và chấm link", async () => {
  const QRCode = (await import("qrcode")).default;
  const qr = await QRCode.toDataURL("https://secure-vietcombank-xacminh.top/login", { width: 360, margin: 4 });
  const qrPage = await browser.newPage();
  await qrPage.setViewport({ width: 900, height: 700 });
  // Trang http thật (extension không chụp được about:blank).
  await qrPage.goto(`${SAFE}/clean.html`);
  await qrPage.evaluate((src) => {
    document.body.style.cssText = "margin:0;display:grid;place-items:center;height:100vh;background:#fff";
    document.body.innerHTML = `<img src="${src}" width="360" height="360">`;
  }, qr);
  await qrPage.bringToFront();
  // Popup thật mở khi bấm icon; ở đây mở popup trong cửa sổ riêng và chỉ định cửa sổ cần chụp (?win=).
  const winId = await worker.evaluate(async () => (await chrome.tabs.query({ active: true, lastFocusedWindow: true }))[0].windowId);
  const before = new Set(browser.targets());
  await worker.evaluate((id, wid) => chrome.windows.create({ url: `chrome-extension://${id}/popup.html?win=${wid}`, type: "popup", width: 360, height: 600 }), extId, winId);
  const popTarget = await browser.waitForTarget((t) => !before.has(t) && t.url().includes("popup.html"), { timeout: 10000 });
  const pop = await popTarget.page();
  const logs = [];
  pop.on("console", (m) => logs.push(m.text()));
  try {
    await pop.waitForSelector("#scan-qr");
    await pop.click("#scan-qr");
    const out = await waitFor(() => pop.$eval("#qr-result", (e) => {
      const t = e.textContent;
      return /Lừa đảo|Đáng ngờ|An toàn|Không/.test(t) && !/Đang chụp/.test(t) ? t : null;
    }), 30000);
    if (!/secure-vietcombank-xacminh\.top/.test(out) || !/Lừa đảo|Đáng ngờ/.test(out)) {
      throw new Error(`${out.slice(0, 80)} | console: ${logs.join(" / ").slice(0, 200)}`);
    }
    return out.replace(/\s+/g, " ").slice(0, 90);
  } finally {
    await pop.close().catch(() => {});
    await qrPage.close();
  }
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
