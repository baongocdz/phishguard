// Trang kiểm tra công khai: Link / Mã QR / Email / Tin nhắn.
const $ = (id) => document.getElementById(id);
const LABEL = { safe: "An toàn", suspicious: "Đáng ngờ", phishing: "Lừa đảo" };
const COLOR = { safe: "var(--safe)", suspicious: "var(--suspicious)", phishing: "var(--phishing)" };
const SOURCE = {
  blacklist: "Danh sách đen", whitelist: "Danh sách tin cậy", cache: "Kết quả đã lưu", safebrowsing: "Google Safe Browsing",
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

// Icon lấy từ bộ <symbol> trong index.html.
function icon(id) {
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("class", "icon");
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS(NS, "use");
  use.setAttribute("href", `#${id}`);
  svg.append(use);
  return svg;
}

const ADVICE = {
  phishing: "Đừng bấm link, đừng nhập mật khẩu, mã OTP hay thông tin thẻ, và không chuyển tiền.",
  suspicious: "Có dấu hiệu bất thường. Kiểm tra kỹ địa chỉ và người gửi trước khi nhập bất kỳ thông tin nào.",
  safe: "Chưa phát hiện dấu hiệu lừa đảo. Dù vậy, đừng bao giờ đưa mã OTP cho người khác.",
};

function showBox(cls, ...children) {
  const box = $("result");
  box.className = cls;
  box.replaceChildren(...children);
  box.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function showLoading(text) {
  showBox("result", el("p", { class: "loading" }, el("span", { class: "spinner" }), text));
}

function showError(err) {
  showBox("result", el("p", { class: "error" }, "⚠ " + (err.message || err)));
}

// Phần đầu kết quả: vòng điểm + kết luận + lời khuyên.
function resultHead(verdict, pct, title, advice, meta = []) {
  const gauge = pct === null ? "" : el("div", { class: "gauge", style: `--p:${pct};--c:${COLOR[verdict]}` },
    el("div", {}, el("b", {}, pct), el("small", {}, "/100")));
  return el("div", { class: "res-head" }, gauge,
    el("div", {},
      el("p", { class: "res-title" }, icon(verdict === "safe" ? "i-check" : "i-alert"), title),
      el("p", { class: "advice" }, advice),
      meta.length ? el("div", { class: "res-meta" }, meta.map((m) => el("span", {}, m))) : ""));
}

// target: {label, value, url?, hostname?} – thông tin để hiển thị và để báo cáo sai.
function showResult(r, target, extra = []) {
  const pct = Math.round(r.score * 100);
  // Explainable AI: mỗi lớp (danh sách, luật, học máy, Gemini...) góp bao nhiêu điểm.
  const breakdown = r.breakdown || [];
  const explained = new Set(breakdown.map((s) => s.label));
  const extraReasons = r.reasons.filter((x) => !explained.has(x)); // lý do chi tiết của Gemini
  const why = breakdown.length ? explainTable(breakdown) : "";
  const reasons = extraReasons.length
    ? el("div", {}, breakdown.length ? el("p", { class: "muted" }, "Chi tiết từ AI:") : "",
        el("ul", {}, extraReasons.map((x) => el("li", {}, x))))
    : breakdown.length ? "" : el("p", { class: "muted" }, "Không phát hiện dấu hiệu bất thường.");

  const children = [
    resultHead(r.verdict, pct, LABEL[r.verdict] || r.verdict, ADVICE[r.verdict] || "",
      [`Mức nguy hiểm ${pct}/100`, `Nguồn: ${SOURCE[r.source] || r.source}`]),
    target ? targetLine(target.label, target.value) : "",
    ...extra,
    why,
    reasons,
  ];
  if (target && target.url) children.push(reportBox(target, r));
  showBox(`result ${r.verdict}`, ...children);
}

function targetLine(label, value) {
  return el("p", { class: "target" }, el("b", {}, label), el("span", { class: "mono" }, value));
}

const LAYER = {
  list: "Danh sách", intel: "Google Safe Browsing", rule: "Bộ luật", ml: "Học máy", ai: "AI Gemini", link: "Link rút gọn",
  age: "Tuổi tên miền", community: "Cộng đồng báo cáo",
};

function explainTable(signals) {
  const rows = signals.map((s) => el("div", { class: "bd-row" },
    el("span", { class: `bd-tag ${s.layer}` }, LAYER[s.layer] || s.layer),
    el("span", {}, s.label),
    el("span", { class: "bd-pts" }, s.points > 0 ? `+${s.points}` : "0")));
  return el("div", { class: "bd" }, el("p", { class: "bd-title" }, icon("i-layers"), "Vì sao ra kết quả này?"), ...rows);
}

function reportBox(target, r) {
  const wrap = el("div", { class: "row" });
  const kind = r.verdict === "safe" ? "phishing" : "false_positive";
  const btn = el("button", { class: "ghost" }, icon(kind === "phishing" ? "i-flag" : "i-check"),
    kind === "phishing" ? "Báo đây là lừa đảo" : "Báo kết quả sai (trang an toàn)");
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
$("url-btn").addEventListener("click", (e) => withButton(e.currentTarget, runUrlCheck));
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

// Đã đọc được nội dung mã QR (từ ảnh hoặc camera): kiểm tra link bên trong.
async function handleQrText(text) {
  const u = parseUrl(text);
  if (!u || !/^https?:$/.test(u.protocol)) {
    showBox("result suspicious",
      resultHead("suspicious", null, "Mã QR không chứa đường link web",
        "Cẩn thận nếu mã QR yêu cầu chuyển tiền, đăng nhập Wi-Fi lạ hoặc mở ứng dụng."),
      targetLine("Nội dung", text));
    return;
  }
  showLoading("Đã đọc mã QR, đang kiểm tra link…");
  const r = await checkUrl(u, "qr");
  showResult(r, { label: "Link trong mã QR", value: u.href, url: u.href, hostname: u.hostname });
}

async function handleQrFile(file) {
  if (!file || !file.type.startsWith("image/")) return showError("Hãy chọn một file ảnh.");
  showLoading("Đang đọc mã QR…");
  try {
    const code = await decodeQr(file);
    if (!code || !code.data) return showError("Không tìm thấy mã QR trong ảnh. Thử ảnh rõ hơn hoặc cắt sát mã QR.");
    await handleQrText(code.data);
  } catch (e) {
    showError(e);
  }
}

// ---------- Quét QR bằng camera (điện thoại: camera sau) ----------
let camStream = null;

function stopCamera() {
  camStream?.getTracks().forEach((t) => t.stop());
  camStream = null;
  $("cam-box").classList.add("hidden");
  $("cam-stop").classList.add("hidden");
  $("cam-btn").classList.remove("hidden");
}

async function startCamera() {
  if (!navigator.mediaDevices?.getUserMedia) {
    return showError("Trình duyệt không hỗ trợ camera (cần mở trang bằng https).");
  }
  try {
    camStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" } }, audio: false });
  } catch (e) {
    return showError("Không mở được camera: hãy cho phép trang dùng camera rồi thử lại.");
  }
  const video = $("cam-video");
  video.srcObject = camStream;
  await video.play();
  $("cam-box").classList.remove("hidden");
  $("cam-stop").classList.remove("hidden");
  $("cam-btn").classList.add("hidden");
  $("cam-status").textContent = "Đưa mã QR vào khung…";
  const canvas = $("qr-canvas");
  const ctx = canvas.getContext("2d", { willReadFrequently: true });

  const scan = async () => {
    if (!camStream) return;
    if (video.readyState >= video.HAVE_ENOUGH_DATA && video.videoWidth) {
      const scale = Math.min(1, 720 / Math.max(video.videoWidth, video.videoHeight));
      canvas.width = Math.round(video.videoWidth * scale);
      canvas.height = Math.round(video.videoHeight * scale);
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const img = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const code = jsQR(img.data, img.width, img.height, { inversionAttempts: "dontInvert" });
      if (code?.data) {
        stopCamera();
        $("cam-status").textContent = "Đã đọc được mã QR.";
        if (navigator.vibrate) navigator.vibrate(80);
        try { await handleQrText(code.data); } catch (e) { showError(e); }
        return;
      }
    }
    requestAnimationFrame(scan);
  };
  requestAnimationFrame(scan);
}
$("cam-btn").addEventListener("click", startCamera);
$("cam-stop").addEventListener("click", () => { stopCamera(); $("cam-status").textContent = ""; });
document.querySelectorAll(".tab").forEach((b) => b.addEventListener("click", () => { if (camStream) stopCamera(); }));

// Cài như ứng dụng (PWA)
if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
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
$("em-btn").addEventListener("click", (e) => withButton(e.currentTarget, runEmailCheck));
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
  const extra = links.length ? [targetLine("Link trong tin", links.map((l) => l.href).join(", "))] : [];
  showResult(r, null, extra);
}
$("sms-btn").addEventListener("click", (e) => withButton(e.currentTarget, runSmsCheck));
$("sms-sample").addEventListener("click", (e) => {
  e.preventDefault();
  $("sms-body").value = "[VCB] Tai khoan cua Quy khach bi tam khoa do dang nhap bat thuong. Vui long truy cap https://vietcombank-xacminh.click de xac minh trong 24h, nhap ma OTP de mo khoa.";
});
