// Trang kiểm tra công khai: Link / Mã QR / Email / Tin nhắn.
const $ = (id) => document.getElementById(id);
const LABEL = { safe: "An toàn", suspicious: "Đáng ngờ", phishing: "Lừa đảo" };
const COLOR = { safe: "var(--safe)", suspicious: "var(--suspicious)", phishing: "var(--phishing)" };
const SOURCE = {
  blacklist: "Danh sách đen", whitelist: "Danh sách tin cậy", cache: "Kết quả đã lưu",
  heuristic: "Bộ luật + học máy", gemini: "Bộ luật + AI Gemini", email: "Bộ luật email",
};
const URL_RE = /\bhttps?:\/\/[^\s<>"')]+/gi;

// ---------- Tabs ----------
document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b === btn));
    document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("hidden", p.id !== `tab-${btn.dataset.tab}`));
    $("result").classList.add("hidden");
  });
});

// ---------- Gọi API ----------
async function post(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (res.status === 429) throw new Error("Bạn kiểm tra quá nhanh, đợi một phút rồi thử lại.");
  if (!res.ok) throw new Error(`Máy chủ báo lỗi (${res.status}).`);
  return res.json();
}

function parseUrl(raw) {
  let text = raw.trim();
  if (!text) return null;
  if (!/^[a-z][a-z0-9+.-]*:\/\//i.test(text)) text = "https://" + text;
  try {
    const u = new URL(text);
    return u.hostname ? u : null;
  } catch {
    return null;
  }
}

async function checkUrl(u, kind) {
  return post("/analyze", {
    url: u.href, hostname: u.hostname, protocol: u.protocol, title: "",
    formCount: 0, hasPasswordField: false, linkCount: 0, externalLinkCount: 0,
    textSnippet: "", kind,
  });
}

// ---------- Hiển thị kết quả ----------
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  Object.entries(attrs).forEach(([k, v]) => (k === "class" ? (node.className = v) : node.setAttribute(k, v)));
  children.flat().forEach((c) => node.append(c instanceof Node ? c : document.createTextNode(String(c))));
  return node;
}

function showLoading(text) {
  const box = $("result");
  box.className = "result";
  box.replaceChildren(el("p", { class: "muted" }, text));
}

function showError(err) {
  const box = $("result");
  box.className = "result";
  box.replaceChildren(el("p", { class: "danger" }, "⚠ " + (err.message || err)));
}

// target: {label, value, url?, hostname?} – thông tin để hiển thị và để báo cáo sai.
function showResult(r, target, extra = []) {
  const box = $("result");
  box.className = `result ${r.verdict}`;
  const pct = Math.round(r.score * 100);
  const meter = el("div", { class: "meter" }, el("div", { style: `width:${Math.max(pct, 3)}%;background:${COLOR[r.verdict]}` }));
  const reasons = r.reasons.length
    ? el("ul", {}, r.reasons.map((x) => el("li", {}, x)))
    : el("p", { class: "muted" }, "Không phát hiện dấu hiệu bất thường.");

  const children = [
    el("div", {}, el("span", { class: `chip ${r.verdict}` }, `${LABEL[r.verdict]}`), "  ",
      el("span", { class: "muted" }, `Mức nguy hiểm ${pct}/100 · Nguồn: ${SOURCE[r.source] || r.source}`)),
    meter,
    target ? el("p", { class: "mono" }, `${target.label}: ${target.value}`) : "",
    ...extra,
    reasons,
  ];
  if (target && target.url) children.push(reportBox(target, r));
  box.replaceChildren(...children);
}

function reportBox(target, r) {
  const wrap = el("div", { class: "row" });
  const kind = r.verdict === "safe" ? "phishing" : "false_positive";
  const btn = el("button", { class: "ghost" },
    kind === "phishing" ? "🚩 Báo đây là lừa đảo" : "✅ Báo kết quả sai (trang an toàn)");
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    try {
      await post("/report", { url: target.url, hostname: target.hostname || "", kind, note: "web" });
      btn.textContent = "Cảm ơn! Quản trị viên sẽ xem xét.";
    } catch (e) {
      btn.textContent = "Gửi báo cáo thất bại";
    }
  });
  wrap.append(btn);
  return wrap;
}

async function withButton(btn, fn) {
  btn.disabled = true;
  try { await fn(); } catch (e) { showError(e); } finally { btn.disabled = false; }
}

// ---------- Link ----------
async function runUrlCheck() {
  const u = parseUrl($("url-input").value);
  if (!u) return showError("Đường link không hợp lệ.");
  showLoading("Đang kiểm tra… (lần đầu có thể mất ~30 giây nếu máy chủ đang ngủ)");
  const r = await checkUrl(u, "manual");
  showResult(r, { label: "Link", value: u.href, url: u.href, hostname: u.hostname });
}
$("url-btn").addEventListener("click", (e) => withButton(e.target, runUrlCheck));
$("url-input").addEventListener("keydown", (e) => { if (e.key === "Enter") $("url-btn").click(); });
document.querySelectorAll(".sample").forEach((a) => a.addEventListener("click", (e) => {
  e.preventDefault();
  $("url-input").value = a.dataset.url;
  $("url-btn").click();
}));

// ---------- QR ----------
async function decodeQr(file) {
  const img = await createImageBitmap(file);
  const canvas = $("qr-canvas");
  const scale = Math.min(1, 1600 / Math.max(img.width, img.height));
  canvas.width = Math.round(img.width * scale);
  canvas.height = Math.round(img.height * scale);
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
  const data = ctx.getImageData(0, 0, canvas.width, canvas.height);
  return jsQR(data.data, data.width, data.height, { inversionAttempts: "attemptBoth" });
}

async function handleQrFile(file) {
  if (!file || !file.type.startsWith("image/")) return showError("Hãy chọn một file ảnh.");
  showLoading("Đang đọc mã QR…");
  try {
    const code = await decodeQr(file);
    if (!code || !code.data) return showError("Không tìm thấy mã QR trong ảnh. Thử ảnh rõ hơn hoặc cắt sát mã QR.");
    const u = parseUrl(code.data);
    if (!u || !/^https?:$/.test(u.protocol)) {
      const box = $("result");
      box.className = "result suspicious";
      box.replaceChildren(
        el("p", {}, "Mã QR không chứa đường link web. Nội dung:"),
        el("p", { class: "mono" }, code.data),
        el("p", { class: "muted" }, "Cẩn thận nếu mã QR yêu cầu chuyển tiền, đăng nhập Wi-Fi lạ hoặc mở ứng dụng."),
      );
      return;
    }
    showLoading("Đã đọc mã QR, đang kiểm tra link…");
    const r = await checkUrl(u, "qr");
    showResult(r, { label: "Link trong mã QR", value: u.href, url: u.href, hostname: u.hostname });
  } catch (e) {
    showError(e);
  }
}
$("qr-file").addEventListener("change", (e) => handleQrFile(e.target.files[0]));
const drop = $("qr-drop");
["dragenter", "dragover"].forEach((t) => drop.addEventListener(t, () => drop.classList.add("over")));
["dragleave", "drop"].forEach((t) => drop.addEventListener(t, () => drop.classList.remove("over")));
document.addEventListener("paste", (e) => {
  const item = [...(e.clipboardData?.items || [])].find((i) => i.type.startsWith("image/"));
  if (!item) return;
  document.querySelector('.tab[data-tab="qr"]').click();
  handleQrFile(item.getAsFile());
});

// ---------- Email ----------
function linksFrom(text) {
  return [...new Set(text.match(URL_RE) || [])].slice(0, 100).map((href) => ({ text: href, href }));
}

async function runEmailCheck() {
  const body = $("em-body").value;
  const req = {
    sender: $("em-from").value, replyTo: $("em-reply").value, subject: $("em-subject").value,
    body, links: [...(window.__emlLinks || []), ...linksFrom(body)],
  };
  if (!req.sender && !req.subject && !body.trim()) return showError("Hãy nhập ít nhất người gửi, tiêu đề hoặc nội dung.");
  showLoading("Đang phân tích email…");
  const r = await post("/analyze-email", req);
  showResult(r, { label: "Email từ", value: req.sender || "(không rõ)" });
}
$("em-btn").addEventListener("click", (e) => withButton(e.target, runEmailCheck));
// Link lấy từ email mẫu / file .eml chỉ dùng cho đúng email đó: người dùng tự sửa thì bỏ đi.
["em-from", "em-subject", "em-body"].forEach((id) => $(id).addEventListener("input", () => { window.__emlLinks = []; }));
$("em-sample").addEventListener("click", (e) => {
  e.preventDefault();
  window.__emlLinks = [{ text: "https://www.vietcombank.com.vn/xac-minh", href: "https://vcb-xacminh-taikhoan.top/login" }];
  $("em-from").value = "Vietcombank <thongbao@vcb-canhbao.com>";
  $("em-reply").value = "hotro.vcb@gmail.com";
  $("em-subject").value = "[KHẨN] Tài khoản của quý khách sẽ bị tạm khóa trong 24 giờ";
  $("em-body").value = "Kính gửi quý khách,\n\nHệ thống phát hiện đăng nhập bất thường. Tài khoản sẽ bị tạm khóa trong 24 giờ nếu quý khách không xác minh.\nVui lòng truy cập https://www.vietcombank.com.vn/xac-minh và nhập mật khẩu cùng mã OTP để xác minh.\n\nTrân trọng,\nVietcombank";
});

// Đọc file .eml đơn giản: lấy header From/Reply-To/Subject, phần text/plain hoặc text/html.
function decodeWords(s) {
  return s.replace(/=\?([^?]+)\?([bq])\?([^?]*)\?=/gi, (_, cs, enc, txt) => {
    try {
      const bytes = enc.toLowerCase() === "b"
        ? Uint8Array.from(atob(txt), (c) => c.charCodeAt(0))
        : Uint8Array.from(txt.replace(/_/g, " ").replace(/=([0-9a-f]{2})/gi, (m, h) => String.fromCharCode(parseInt(h, 16))), (c) => c.charCodeAt(0));
      return new TextDecoder(cs).decode(bytes);
    } catch { return txt; }
  });
}
function decodeBody(part, encoding) {
  try {
    let bytes;
    if (/base64/i.test(encoding)) bytes = Uint8Array.from(atob(part.replace(/\s+/g, "")), (c) => c.charCodeAt(0));
    else if (/quoted-printable/i.test(encoding)) {
      const s = part.replace(/=\r?\n/g, "").replace(/=([0-9a-f]{2})/gi, (m, h) => String.fromCharCode(parseInt(h, 16)));
      bytes = Uint8Array.from(s, (c) => c.charCodeAt(0));
    } else return part;
    return new TextDecoder("utf-8").decode(bytes);
  } catch { return part; }
}
function parseEml(raw) {
  const [head, ...rest] = raw.split(/\r?\n\r?\n/);
  const headers = {};
  head.replace(/\r?\n[ \t]+/g, " ").split(/\r?\n/).forEach((line) => {
    const i = line.indexOf(":");
    if (i > 0) headers[line.slice(0, i).toLowerCase()] = decodeWords(line.slice(i + 1).trim());
  });
  const bodyRaw = rest.join("\n\n");
  let text = "", html = "";
  const boundary = /boundary="?([^";]+)"?/i.exec(headers["content-type"] || "");
  const parts = boundary ? bodyRaw.split("--" + boundary[1]) : [`Content-Type: ${headers["content-type"] || "text/plain"}\nContent-Transfer-Encoding: ${headers["content-transfer-encoding"] || ""}\n\n${bodyRaw}`];
  for (const p of parts) {
    const [ph, ...pb] = p.replace(/^\r?\n/, "").split(/\r?\n\r?\n/);
    const type = /content-type:\s*([^;\s]+)/i.exec(ph)?.[1]?.toLowerCase() || "";
    const enc = /content-transfer-encoding:\s*(\S+)/i.exec(ph)?.[1] || "";
    const content = decodeBody(pb.join("\n\n"), enc);
    if (type === "text/plain" && !text) text = content;
    if (type === "text/html" && !html) html = content;
  }
  const links = [];
  if (html) {
    const doc = new DOMParser().parseFromString(html, "text/html");
    doc.querySelectorAll("a[href]").forEach((a) => {
      if (/^https?:/i.test(a.getAttribute("href"))) links.push({ text: a.textContent.trim().slice(0, 300), href: a.getAttribute("href") });
    });
    if (!text) text = doc.body?.innerText || doc.body?.textContent || "";
  }
  return { from: headers["from"] || "", replyTo: headers["reply-to"] || "", subject: headers["subject"] || "", body: text.trim(), links };
}
$("em-file").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const m = parseEml(await file.text());
  $("em-from").value = m.from; $("em-reply").value = m.replyTo; $("em-subject").value = m.subject;
  $("em-body").value = m.body.slice(0, 20000);
  window.__emlLinks = m.links.slice(0, 200);
  $("em-btn").click();
});

// ---------- Tin nhắn ----------
async function runSmsCheck() {
  const body = $("sms-body").value.trim();
  if (!body) return showError("Hãy dán nội dung tin nhắn.");
  showLoading("Đang phân tích tin nhắn…");
  const links = linksFrom(body);
  const r = await post("/analyze-email", { sender: "", replyTo: "", subject: "", body, links });
  const extra = links.length ? [el("p", { class: "muted" }, `Link trong tin: ${links.map((l) => l.href).join(", ")}`)] : [];
  showResult(r, null, extra);
}
$("sms-btn").addEventListener("click", (e) => withButton(e.target, runSmsCheck));
$("sms-sample").addEventListener("click", (e) => {
  e.preventDefault();
  $("sms-body").value = "[VCB] Tai khoan cua Quy khach bi tam khoa do dang nhap bat thuong. Vui long truy cap https://vietcombank-xacminh.click de xac minh trong 24h, nhap ma OTP de mo khoa.";
});
