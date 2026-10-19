// Chạy trên mail.google.com: đọc email đang mở, gửi cho backend phân tích và
// hiện cảnh báo ngay trên email. Bộ chọn DOM dựa theo giao diện Gmail hiện tại
// (h2.hP = tiêu đề, span.gD = người gửi, div.a3s = nội dung) nên có thể phải
// cập nhật nếu Gmail đổi giao diện.
import type { AnalysisResult, EmailInfo, ExtMessage } from "./types";

const BANNER_CLASS = "phishguard-email-banner";
const analyzed = new Map<string, AnalysisResult | null>();
// Phân tích thất bại (máy chủ bận / giới hạn lượt gọi / mất mạng): lùi thời gian thử lại 15 s → 30 s → … tối đa 2 phút.
// Không lùi thì cứ 0,6 s lại gửi một lần → bị giới hạn lượt gọi (429) mãi không thoát ra được.
const failed = new Map<string, { until: number; delay: number }>();

async function enabled(): Promise<boolean> {
  const { gmailScan } = await chrome.storage.local.get("gmailScan");
  return gmailScan !== false; // mặc định bật, tắt được trong popup
}

// Gmail giữ lại DOM của thư đã xem (chỉ ẩn đi) → luôn chọn phần tử ĐANG HIỂN THỊ.
const isVisible = (el: Element) => el.getClientRects().length > 0;
const visibleSubject = () => Array.from(document.querySelectorAll<HTMLElement>("h2.hP")).find(isVisible);

function readOpenEmail(): { key: string; info: EmailInfo; anchor: HTMLElement } | null {
  const subject = visibleSubject()?.innerText.trim() ?? "";
  // Một cuộc hội thoại có thể có nhiều thư; lấy thư cuối cùng đang mở VÀ đang hiện trên màn hình
  // (Gmail giữ sẵn các khung div.a3s bị ẩn; chèn banner vào đó thì người dùng không thấy).
  const bodies = Array.from(document.querySelectorAll<HTMLElement>("div.a3s"))
    .filter((b) => b.getClientRects().length > 0 && b.innerText.trim());
  const body = bodies.at(-1);
  if (!body) return null;
  const message = body.closest<HTMLElement>("div.adn, div.gs") ?? body.parentElement!;
  const senderEl = message.querySelector<HTMLElement>("span.gD[email]") ??
    document.querySelector<HTMLElement>("span.gD[email]");
  const name = senderEl?.getAttribute("name") ?? senderEl?.innerText ?? "";
  const email = senderEl?.getAttribute("email") ?? "";

  const links = Array.from(body.querySelectorAll<HTMLAnchorElement>("a[href]"))
    .filter((a) => /^https?:/i.test(a.href) && a.href.length <= 2048) // link quá dài: server từ chối cả email
    .slice(0, 200)
    .map((a) => ({ text: a.innerText.trim().slice(0, 300), href: a.href }));

  const text = body.innerText.replace(/\s+/g, " ").trim().slice(0, 20000);
  const info: EmailInfo = { sender: email ? `${name} <${email}>` : name, replyTo: "", subject, body: text, links };
  const key = `${info.sender}|${subject}|${text.slice(0, 200)}`;
  return { key, info, anchor: body };
}

const hasBanner = () => Array.from(document.querySelectorAll(`.${BANNER_CLASS}`)).some(isVisible);

function bannerShell(anchor: HTMLElement, cls: string): HTMLDivElement {
  document.querySelectorAll(`.${BANNER_CLASS}`).forEach((b) => b.remove());
  const host = document.createElement("div");
  host.className = BANNER_CLASS;
  const root = host.attachShadow({ mode: "open" });
  const style = document.createElement("style");
  style.textContent = `
    .box { margin: 8px 0 12px; padding: 10px 14px; border-radius: 8px; color: #fff;
           font: 14px/1.45 system-ui, sans-serif; }
    .phishing { background: #c62828; } .suspicious { background: #ef6c00; }
    .safe, .loading { padding: 6px 12px; font-size: 13px; color: #1e4620; background: #e7f6ee; border: 1px solid #b7dfc5; }
    .loading { color: #5d6b82; background: #f5f7fb; border-color: #e2e7f0; }
    ul { margin: 6px 0 0 18px; padding: 0; }
  `;
  const box = document.createElement("div");
  box.className = `box ${cls}`;
  root.append(style, box);
  // Đặt ngay dưới tiêu đề email: luôn nhìn thấy khi mở thư, kể cả thread dài nhiều thư
  // (đặt trên nội dung thư cuối thì hay bị cuộn khuất). Không có tiêu đề thì đặt trên nội dung.
  const subjectRow = visibleSubject()?.parentElement;
  if (subjectRow?.parentElement) subjectRow.after(host);
  else anchor.parentElement?.insertBefore(host, anchor);
  return box;
}

function showRetry(anchor: HTMLElement, until: number): void {
  const s = Math.max(1, Math.round((until - Date.now()) / 1000));
  bannerShell(anchor, "loading").textContent = `🛡️ PhishGuard chưa kiểm tra được email này (máy chủ bận hoặc mất mạng), sẽ thử lại sau ${s} giây.`;
}

function showLoading(anchor: HTMLElement): void {
  bannerShell(anchor, "loading").textContent = "🛡️ PhishGuard đang kiểm tra email này…";
}

function showBanner(anchor: HTMLElement, r: AnalysisResult): void {
  if (r.verdict === "safe") {
    bannerShell(anchor, "safe").textContent =
      "✓ PhishGuard đã kiểm tra: chưa thấy dấu hiệu lừa đảo trong email này. (Bấm icon PhishGuard để xem chi tiết)";
    return;
  }
  const box = bannerShell(anchor, r.verdict);
  const title = document.createElement("strong");
  title.textContent = r.verdict === "phishing"
    ? `⚠ PhishGuard: email này có dấu hiệu LỪA ĐẢO (mức ${Math.round(r.score * 100)}/100)`
    : `⚠ PhishGuard: email này có dấu hiệu đáng ngờ (mức ${Math.round(r.score * 100)}/100)`;
  const list = document.createElement("ul");
  for (const reason of r.reasons) {
    const li = document.createElement("li");
    li.textContent = reason; // textContent: lý do có thể do AI sinh ra từ nội dung email
    list.append(li);
  }
  const tip = document.createElement("div");
  tip.textContent = "Không bấm link, không nhập mật khẩu/OTP, không chuyển tiền theo yêu cầu trong email.";
  tip.style.marginTop = "6px";
  box.append(title, list, tip);
}

async function check(): Promise<void> {
  if (!(await enabled())) return;
  const mail = readOpenEmail();
  if (!mail) return;
  const fail = failed.get(mail.key);
  if (fail && Date.now() < fail.until) {
    if (!hasBanner()) showRetry(mail.anchor, fail.until);
    return;
  }
  if (analyzed.has(mail.key)) {
    const r = analyzed.get(mail.key);
    if (r && !hasBanner()) showBanner(mail.anchor, r);
    return;
  }
  analyzed.set(mail.key, null); // đánh dấu đang xử lý, tránh gửi trùng
  showLoading(mail.anchor);
  const r: AnalysisResult | null = await chrome.runtime.sendMessage(
    { type: "ANALYZE_EMAIL", payload: mail.info, pageUrl: location.href } satisfies ExtMessage,
  ).catch(() => null);
  if (!r) {
    analyzed.delete(mail.key); // thử lại sau, không thử ngay
    const delay = Math.min((fail?.delay ?? 7500) * 2, 120_000);
    failed.set(mail.key, { until: Date.now() + delay, delay });
    if (readOpenEmail()?.key === mail.key) showRetry(mail.anchor, Date.now() + delay);
    return;
  }
  failed.delete(mail.key);
  analyzed.set(mail.key, r);
  // Người dùng đã chuyển sang thư khác trong lúc chờ: không gắn kết quả vào nhầm thư.
  if (readOpenEmail()?.key === mail.key) showBanner(mail.anchor, r);
}

// Kiểm tra tối đa mỗi 0,6 giây khi Gmail đổi DOM. (Không "đợi DOM đứng yên" vì Gmail đổi DOM gần như
// liên tục — đồng hồ, khung chat — nên mốc đó không bao giờ tới: mở thư khác mà không được kiểm tra.)
let scheduled = false;
function schedule(delay = 600): void {
  if (scheduled) return;
  scheduled = true;
  window.setTimeout(() => {
    scheduled = false;
    void check().catch(() => {});
  }, delay);
}

// Gmail là ứng dụng một trang: theo dõi DOM thay đổi để biết khi mở email khác.
const observer = new MutationObserver(() => {
  // Extension vừa được cập nhật / tải lại: bản script cũ còn chạy trên tab này đã mất kết nối
  // (chrome.storage thành undefined) → tự dừng. Tải lại tab Gmail để chạy bản mới.
  if (!chrome.runtime?.id) {
    observer.disconnect();
    return;
  }
  schedule();
});
observer.observe(document.body, { childList: true, subtree: true });
// Mở thư khác = đổi #… trên URL; kiểm tra lại cả lúc Gmail vẽ xong thư.
window.addEventListener("hashchange", () => {
  schedule(300);
  window.setTimeout(() => schedule(), 1500);
});
void check().catch(() => {}); // email đã mở sẵn lúc tải trang (vd mở bằng link thẳng tới thư)
