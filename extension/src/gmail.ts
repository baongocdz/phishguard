// Chạy trên mail.google.com: đọc email đang mở, gửi cho backend phân tích và
// hiện cảnh báo ngay trên email. Bộ chọn DOM dựa theo giao diện Gmail hiện tại
// (h2.hP = tiêu đề, span.gD = người gửi, div.a3s = nội dung) nên có thể phải
// cập nhật nếu Gmail đổi giao diện.
import type { AnalysisResult, EmailInfo, ExtMessage } from "./types";

const BANNER_CLASS = "phishguard-email-banner";
const analyzed = new Map<string, AnalysisResult | null>();

async function enabled(): Promise<boolean> {
  const { gmailScan } = await chrome.storage.local.get("gmailScan");
  return gmailScan !== false; // mặc định bật, tắt được trong popup
}

function readOpenEmail(): { key: string; info: EmailInfo; anchor: HTMLElement } | null {
  const subject = document.querySelector<HTMLElement>("h2.hP")?.innerText.trim() ?? "";
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
    .filter((a) => /^https?:/i.test(a.href))
    .slice(0, 200)
    .map((a) => ({ text: a.innerText.trim().slice(0, 300), href: a.href }));

  const text = body.innerText.replace(/\s+/g, " ").trim().slice(0, 20000);
  const info: EmailInfo = { sender: email ? `${name} <${email}>` : name, replyTo: "", subject, body: text, links };
  const key = `${info.sender}|${subject}|${text.slice(0, 200)}`;
  return { key, info, anchor: body };
}

function bannerShell(anchor: HTMLElement, cls: string): HTMLDivElement {
  anchor.parentElement?.querySelector(`.${BANNER_CLASS}`)?.remove();
  const host = document.createElement("div");
  host.className = BANNER_CLASS;
  const root = host.attachShadow({ mode: "open" });
  const style = document.createElement("style");
  style.textContent = `
    .box { margin: 0 0 12px; padding: 10px 14px; border-radius: 8px; color: #fff;
           font: 14px/1.45 system-ui, sans-serif; }
    .phishing { background: #c62828; } .suspicious { background: #ef6c00; }
    .safe, .loading { padding: 6px 12px; font-size: 13px; color: #1e4620; background: #e7f6ee; border: 1px solid #b7dfc5; }
    .loading { color: #5d6b82; background: #f5f7fb; border-color: #e2e7f0; }
    ul { margin: 6px 0 0 18px; padding: 0; }
  `;
  const box = document.createElement("div");
  box.className = `box ${cls}`;
  root.append(style, box);
  anchor.parentElement?.insertBefore(host, anchor);
  return box;
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

let timer: number | undefined;

async function check(): Promise<void> {
  if (!(await enabled())) return;
  const mail = readOpenEmail();
  if (!mail) return;
  if (analyzed.has(mail.key)) {
    const r = analyzed.get(mail.key);
    if (r && !mail.anchor.parentElement?.querySelector(`.${BANNER_CLASS}`)) showBanner(mail.anchor, r);
    return;
  }
  analyzed.set(mail.key, null); // đánh dấu đang xử lý, tránh gửi trùng
  showLoading(mail.anchor);
  const r: AnalysisResult | null = await chrome.runtime.sendMessage(
    { type: "ANALYZE_EMAIL", payload: mail.info } satisfies ExtMessage,
  ).catch(() => null);
  if (!r) {
    analyzed.delete(mail.key); // lỗi mạng: lần sau thử lại
    mail.anchor.parentElement?.querySelector(`.${BANNER_CLASS}`)?.remove();
    return;
  }
  analyzed.set(mail.key, r);
  showBanner(mail.anchor, r);
}

// Gmail là ứng dụng một trang: theo dõi DOM thay đổi để biết khi mở email khác.
const observer = new MutationObserver(() => {
  // Extension vừa được cập nhật / tải lại: bản script cũ còn chạy trên tab này đã mất kết nối
  // (chrome.storage thành undefined) → tự dừng. Tải lại tab Gmail để chạy bản mới.
  if (!chrome.runtime?.id) {
    observer.disconnect();
    return;
  }
  clearTimeout(timer);
  timer = window.setTimeout(() => void check().catch(() => {}), 800);
});
observer.observe(document.body, { childList: true, subtree: true });
