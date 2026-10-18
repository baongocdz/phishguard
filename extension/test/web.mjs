// Test tự động trang web kiểm tra (/), dashboard (/dashboard) và /about trong Chrome thật.
// Chạy: npm run web-test                       (backend ở máy: http://localhost:8000)
//       npm run web-test -- <url> <mã quản trị> (vd bản trên Render)
// Lưu ý: backend ở máy và Render dùng CHUNG database → test tự xóa báo cáo thử mà nó tạo.
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import puppeteer from "puppeteer";
import QRCode from "qrcode";

const BASE = (process.argv[2] || "http://localhost:8000").replace(/\/$/, "");
const ADMIN = process.argv[3] || process.env.PHISHGUARD_ADMIN_TOKEN || "";
const browser = await puppeteer.launch({ headless: !process.env.HEADFUL });
const page = await browser.newPage();
await page.setViewport({ width: 1200, height: 900 });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));

const results = [];
async function test(name, fn) {
  const t = Date.now();
  try {
    const info = await fn();
    results.push(true);
    console.log(`✅ ${name.padEnd(46)} ${String(Date.now() - t).padStart(5)} ms  ${info ?? ""}`);
  } catch (e) {
    results.push(false);
    console.log(`❌ ${name.padEnd(46)} ${String(Date.now() - t).padStart(5)} ms  ${e.message.split("\n")[0]}`);
  }
}
const resultText = () => page.$eval("#result", (e) => e.innerText);
async function waitResult() {
  await page.waitForFunction(() => {
    const r = document.getElementById("result");
    return r && !r.classList.contains("hidden") && /An toàn|Đáng ngờ|Lừa đảo|⚠/.test(r.innerText);
  }, { timeout: 60000 });
  return page.$eval("#result", (e) => ({ cls: e.className, text: e.innerText }));
}

await test("Trang chủ tải được, không lỗi JavaScript", async () => {
  await page.goto(BASE + "/", { waitUntil: "networkidle0", timeout: 90000 });
  if (errors.length) throw new Error(errors.join("; "));
  return await page.title();
});

await test("Tab Link: tên miền giả → Lừa đảo + giải thích", async () => {
  await page.click('.tab[data-tab="url"]');
  await page.$eval("#url-input", (e) => (e.value = ""));
  await page.type("#url-input", "https://secure-vietcombank-xacminh.top/login");
  await page.click("#url-btn");
  const r = await waitResult();
  if (!r.cls.includes("phishing")) throw new Error(r.text.slice(0, 80));
  const rows = await page.$$eval(".bd-row", (rs) => rs.length);
  if (!rows) throw new Error("thiếu phần giải thích (kết quả cache cũ?)");
  return `${rows} dòng giải thích`;
});

await test("Tab Link: trang thật → An toàn", async () => {
  await page.$eval("#url-input", (e) => (e.value = ""));
  await page.type("#url-input", "vnexpress.net");
  await page.click("#url-btn");
  const r = await waitResult();
  if (!r.cls.includes("safe")) throw new Error(r.text.slice(0, 80));
  return "an toàn";
});

await test("Tab Mã QR: tải ảnh QR chứa link giả → Lừa đảo", async () => {
  const dir = mkdtempSync(join(tmpdir(), "pg-qr-"));
  const file = join(dir, "qr.png");
  writeFileSync(file, await QRCode.toBuffer("https://paypal-verify-account.com/signin", { width: 400, margin: 4 }));
  await page.click('.tab[data-tab="qr"]');
  const input = await page.$("#qr-file");
  await input.uploadFile(file);
  const r = await waitResult();
  if (!r.cls.includes("phishing") || !r.text.includes("paypal-verify-account.com")) throw new Error(r.text.slice(0, 100));
  return "đọc được mã QR và chấm đúng";
});

await test("Tab Email: email mẫu → Lừa đảo, nhiều lý do", async () => {
  await page.click('.tab[data-tab="email"]');
  await page.click("#em-sample");
  await page.click("#em-btn");
  const r = await waitResult();
  if (!r.cls.includes("phishing")) throw new Error(r.text.slice(0, 80));
  return `${await page.$$eval(".bd-row", (rs) => rs.length)} tín hiệu`;
});

await test("Tab Tin nhắn: tin mẫu → cảnh báo", async () => {
  await page.click('.tab[data-tab="sms"]');
  await page.click("#sms-sample");
  await page.click("#sms-btn");
  const r = await waitResult();
  if (r.cls.includes("safe")) throw new Error(r.text.slice(0, 80));
  return r.cls.replace("result ", "");
});

await test("Nút báo kết quả sai gửi được", async () => {
  await page.click('.tab[data-tab="url"]');
  await page.$eval("#url-input", (e) => (e.value = ""));
  await page.type("#url-input", "https://phishguard-e2e-report.example/");
  await page.click("#url-btn");
  await waitResult();
  const btn = await page.waitForSelector("#result .row .ghost");
  await btn.click();
  await page.waitForFunction(() => /Cảm ơn/.test(document.querySelector("#result .row .ghost")?.textContent || ""), { timeout: 20000 });
  return "đã gửi";
});

await test("Trang /about: số liệu + bảng đánh giá + ảnh", async () => {
  await page.goto(BASE + "/about", { waitUntil: "networkidle0" });
  await page.waitForFunction(() => document.querySelectorAll("#metrics tr").length > 1, { timeout: 30000 });
  const info = await page.evaluate(() => ({
    rows: document.querySelectorAll("#metrics tr").length - 1,
    kpis: document.querySelectorAll("#kpis .kpi").length,
    imgsOk: [...document.querySelectorAll(".imgs img")].every((i) => i.complete && i.naturalWidth > 0),
  }));
  if (!info.imgsOk || info.rows < 3) throw new Error(JSON.stringify(info));
  return `${info.kpis} ô số liệu, ${info.rows} dòng đánh giá, ảnh đủ`;
});

if (ADMIN) {
  await test("Dashboard: sai mã → hiện đăng nhập", async () => {
    await page.goto(BASE + "/dashboard");
    await page.evaluate(() => localStorage.setItem("pg_admin_token", "sai-ma"));
    await page.reload({ waitUntil: "networkidle0" });
    await page.waitForFunction(() => !document.getElementById("login").classList.contains("hidden"));
    return await page.$eval("#login-err", (e) => e.textContent);
  });

  await test("Dashboard: đúng mã → biểu đồ, bảng, danh sách", async () => {
    await page.$eval("#token", (e) => (e.value = ""));
    await page.type("#token", ADMIN);
    await page.click("#login-btn");
    await page.waitForFunction(() => !document.getElementById("app").classList.contains("hidden")
      && document.querySelectorAll("#whitelist tr").length > 1, { timeout: 30000 });
    const info = await page.evaluate(() => ({
      kpis: document.querySelectorAll("#kpis .kpi").length,
      charts: [...document.querySelectorAll("canvas")].filter((c) => c.width > 0).length,
      white: document.getElementById("whitelist-count").textContent,
    }));
    return `${info.kpis} ô số, ${info.charts} biểu đồ, ${info.white} tên miền tin cậy`;
  });

  await test("Dashboard: tìm kiếm trong danh sách tin cậy", async () => {
    await page.type('[data-filter="whitelist"]', "vietcombank");
    const rows = await page.$$eval("#whitelist tr", (rs) => rs.length - 1);
    if (rows !== 1) throw new Error(`ra ${rows} dòng`);
    return "lọc còn 1 dòng";
  });

  await test("Dashboard: báo cáo thử xuất hiện rồi xóa được", async () => {
    const res = await page.evaluate(async (token) => {
      const h = { "X-Admin-Token": token };
      const reports = await (await fetch("/admin/reports", { headers: h })).json();
      const mine = reports.filter((r) => r.hostname === "phishguard-e2e-report.example");
      for (const r of mine) await fetch(`/admin/reports/${r.id}`, { method: "DELETE", headers: h });
      return mine.length;
    }, ADMIN);
    if (!res) throw new Error("không thấy báo cáo thử");
    return `đã dọn ${res} báo cáo thử`;
  });
}

await test("Giao diện điện thoại (390px): không tràn ngang", async () => {
  await page.setViewport({ width: 390, height: 844, isMobile: true });
  const widths = {};
  for (const path of ["/", "/about", "/dashboard"]) {
    await page.goto(BASE + path, { waitUntil: "networkidle0" });
    widths[path] = await page.evaluate(() => document.documentElement.scrollWidth);
  }
  const over = Object.entries(widths).filter(([, w]) => w > 392);
  if (over.length) throw new Error(`tràn ngang: ${JSON.stringify(widths)}`);
  return JSON.stringify(widths);
});

if (errors.length) console.log("Lỗi JavaScript trên trang:", errors);
await browser.close();
const passed = results.filter(Boolean).length;
console.log(`\n${passed}/${results.length} đạt.`);
process.exit(passed === results.length && !errors.length ? 0 : 1);
