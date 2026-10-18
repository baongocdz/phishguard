// Dashboard quản trị: đọc /admin/* với header X-Admin-Token.
const $ = (id) => document.getElementById(id);
const LABEL = { safe: "An toàn", suspicious: "Đáng ngờ", phishing: "Lừa đảo" };
const KIND = { page: "Trang web (extension)", qr: "Mã QR", manual: "Link dán vào web", email: "Email / tin nhắn" };
const SOURCE = {
  blacklist: "Danh sách đen", whitelist: "Danh sách tin cậy", cache: "Cache",
  heuristic: "Bộ luật", gemini: "Luật + Gemini", email: "Luật email",
};
const PALETTE = ["#2453d6", "#c62828", "#ef6c00", "#2e7d32", "#7b1fa2", "#00838f", "#6d4c41"];
const charts = {};

function token() {
  try { return localStorage.getItem("pg_admin_token") || ""; } catch { return ""; }
}
function setToken(t) {
  try { t ? localStorage.setItem("pg_admin_token", t) : localStorage.removeItem("pg_admin_token"); } catch {}
}

async function api(path, opts = {}) {
  const res = await fetch(path, {
    ...opts,
    headers: { "Content-Type": "application/json", "X-Admin-Token": token(), ...(opts.headers || {}) },
  });
  if (res.status === 401) { showLogin("Mã quản trị không đúng."); throw new Error("401"); }
  if (!res.ok) throw new Error(`Lỗi ${res.status}`);
  return res.json();
}

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  Object.entries(attrs).forEach(([k, v]) => (k === "class" ? (node.className = v) : node.setAttribute(k, v)));
  children.flat().forEach((c) => node.append(c instanceof Node ? c : document.createTextNode(String(c ?? ""))));
  return node;
}
const chip = (v) => el("span", { class: `chip ${v}` }, LABEL[v] || v);
const fmtTime = (s) => (s ? new Date(s.endsWith?.("Z") || s.includes?.("+") ? s : s + "Z").toLocaleString("vi-VN") : "");

function table(id, head, rows, empty = "Chưa có dữ liệu.") {
  const t = $(id);
  const thead = el("tr", {}, head.map((h) => el("th", {}, h)));
  const body = rows.length ? rows.map((r) => el("tr", {}, r.map((c) => el("td", {}, c)))) : [el("tr", {}, el("td", { colspan: head.length, class: "muted" }, empty))];
  t.replaceChildren(thead, ...body);
}

function drawChart(id, config) {
  charts[id]?.destroy();
  charts[id] = new Chart($(id), config);
}

function showLogin(msg = "") {
  $("app").classList.add("hidden");
  $("login").classList.remove("hidden");
  $("login-err").textContent = msg;
}

async function loadStats() {
  const s = await api(`/admin/stats?days=${$("days").value}`);
  const total = Object.values(s.by_verdict).reduce((a, b) => a + b, 0);
  const kpis = [
    ["Tổng lượt kiểm tra", total],
    ["Lừa đảo", s.by_verdict.phishing || 0],
    ["Đáng ngờ", s.by_verdict.suspicious || 0],
    ["Phát hiện bằng AI", s.by_source.gemini || 0],
    ["Quét mã QR", s.by_kind.qr || 0],
    ["Email / tin nhắn", s.by_kind.email || 0],
    ["Báo cáo người dùng", s.reports],
    ["Danh sách đen / trắng", `${s.blacklist} / ${s.whitelist}`],
  ];
  $("kpis").replaceChildren(...kpis.map(([l, v]) => el("div", { class: "kpi" }, el("div", { class: "v" }, v), el("div", { class: "l" }, l))));

  drawChart("chart-days", {
    type: "bar",
    data: {
      labels: s.per_day.labels.map((d) => d.slice(5)),
      datasets: [
        { label: "An toàn", data: s.per_day.safe, backgroundColor: "#2e7d32" },
        { label: "Đáng ngờ", data: s.per_day.suspicious, backgroundColor: "#ef6c00" },
        { label: "Lừa đảo", data: s.per_day.phishing, backgroundColor: "#c62828" },
      ],
    },
    options: { responsive: true, scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true, ticks: { precision: 0 } } } },
  });
  const pie = (id, obj, names) => drawChart(id, {
    type: "doughnut",
    data: {
      labels: Object.keys(obj).map((k) => names[k] || k),
      datasets: [{ data: Object.values(obj), backgroundColor: PALETTE }],
    },
    options: { plugins: { legend: { position: "bottom" } } },
  });
  pie("chart-source", s.by_source, SOURCE);
  pie("chart-kind", s.by_kind, KIND);

  table("top-hosts", ["Tên miền", "Số lần", "Mức", ""], s.top_hosts.map((h) => [
    el("span", { class: "mono" }, h.hostname), h.count, chip(h.verdict), quickBlock(h.hostname),
  ]));
}

function quickBlock(hostname) {
  const b = el("button", { class: "ghost" }, "⛔ Chặn");
  b.addEventListener("click", async () => {
    await api("/admin/lists/blacklist", { method: "POST", body: JSON.stringify({ domain: hostname }) });
    b.textContent = "Đã chặn";
    b.disabled = true;
    loadLists();
  });
  return b;
}

async function loadEvents() {
  const ev = await api("/admin/events?limit=50");
  table("events", ["Thời gian", "Loại", "Tên miền / người gửi", "Kết luận", "Điểm", "Nguồn"], ev.map((e) => [
    fmtTime(e.at), KIND[e.kind] || e.kind, el("span", { class: "mono" }, e.hostname || "—"), chip(e.verdict), e.score, SOURCE[e.source] || e.source,
  ]), "Chưa có cảnh báo nào.");
}

async function loadReports() {
  const rs = await api("/admin/reports");
  table("reports", ["Thời gian", "Loại báo cáo", "URL", "Ghi chú", "Xử lý"], rs.map((r) => {
    const actions = el("div", { class: "row", style: "margin:0" });
    const target = r.kind === "phishing" ? "blacklist" : "whitelist";
    const accept = el("button", { class: "ghost" }, r.kind === "phishing" ? "⛔ Đưa vào DS đen" : "✅ Đưa vào DS tin cậy");
    accept.addEventListener("click", async () => {
      await api(`/admin/lists/${target}`, { method: "POST", body: JSON.stringify({ domain: r.hostname }) });
      await api(`/admin/reports/${r.id}`, { method: "DELETE" });
      loadReports(); loadLists();
    });
    const dismiss = el("button", { class: "ghost" }, "Bỏ qua");
    dismiss.addEventListener("click", async () => { await api(`/admin/reports/${r.id}`, { method: "DELETE" }); loadReports(); });
    actions.append(accept, dismiss);
    return [fmtTime(r.at), r.kind === "phishing" ? "🚩 Báo lừa đảo" : "✅ Báo chặn nhầm", el("span", { class: "mono" }, r.url), r.note, actions];
  }), "Chưa có báo cáo nào.");
}

async function loadLists() {
  for (const name of ["blacklist", "whitelist"]) {
    const items = await api(`/admin/lists/${name}`);
    table(name, ["Tên miền", "Nguồn", ""], items.map((d) => {
      const del = el("button", { class: "ghost danger" }, "Xóa");
      del.addEventListener("click", async () => {
        await api(`/admin/lists/${name}/${encodeURIComponent(d.domain)}`, { method: "DELETE" });
        loadLists();
      });
      return [el("span", { class: "mono" }, d.domain), d.source || "", del];
    }));
  }
}

document.querySelectorAll("[data-add]").forEach((btn) => btn.addEventListener("click", async () => {
  const name = btn.dataset.add;
  const input = $(name === "blacklist" ? "bl-input" : "wl-input");
  if (!input.value.trim()) return;
  try {
    await api(`/admin/lists/${name}`, { method: "POST", body: JSON.stringify({ domain: input.value }) });
    input.value = "";
    loadLists();
  } catch (e) {
    alert("Tên miền không hợp lệ hoặc lỗi máy chủ.");
  }
}));

async function loadAll() {
  try {
    await loadStats();
    $("login").classList.add("hidden");
    $("app").classList.remove("hidden");
    await Promise.all([loadEvents(), loadReports(), loadLists()]);
  } catch (e) {
    if (e.message !== "401") showLogin("Không tải được dữ liệu: " + e.message);
  }
}

$("login-btn").addEventListener("click", () => { setToken($("token").value.trim()); loadAll(); });
$("token").addEventListener("keydown", (e) => { if (e.key === "Enter") $("login-btn").click(); });
$("logout").addEventListener("click", () => { setToken(""); showLogin(); });
$("refresh").addEventListener("click", loadAll);
$("days").addEventListener("change", loadStats);

token() ? loadAll() : showLogin();
