import { analyzeLocal } from "./analyzer";
import type { AnalysisResult, ExtMessage, PageInfo } from "./types";

function collectPageInfo(): PageInfo {
  const links = Array.from(document.querySelectorAll<HTMLAnchorElement>("a[href]"));
  const externalLinkCount = links.filter((a) => {
    try {
      return new URL(a.href).hostname !== location.hostname;
    } catch {
      return false;
    }
  }).length;

  const formCount = document.forms.length;
  const hasPasswordField = document.querySelector("input[type='password']") !== null;

  return {
    url: location.href,
    hostname: location.hostname,
    protocol: location.protocol,
    title: document.title,
    formCount,
    hasPasswordField,
    linkCount: links.length,
    externalLinkCount,
    // Chỉ gửi chữ trên trang khi có form (lúc backend có thể hỏi Gemini),
    // để không đẩy nội dung mọi trang người dùng đọc lên server.
    textSnippet: formCount > 0 || hasPasswordField ? visibleText(TEXT_LIMIT) : "",
    collectedAt: Date.now(),
  };
}

const TEXT_LIMIT = 2000;

function visibleText(limit: number): string {
  return (document.body?.innerText ?? "").replace(/\s+/g, " ").trim().slice(0, limit);
}

const HOST_ID = "phishguard-banner-host";

// Dùng Shadow DOM để CSS của trang web không ảnh hưởng tới banner.
// Dùng textContent (không dùng innerHTML) vì sau này lý do có thể do LLM sinh ra,
// và nội dung đó có thể bị ảnh hưởng bởi chính trang phishing.
function showBanner(result: AnalysisResult): void {
  document.getElementById(HOST_ID)?.remove();

  const host = document.createElement("div");
  host.id = HOST_ID;
  const root = host.attachShadow({ mode: "open" });

  const style = document.createElement("style");
  style.textContent = `
    .bar { position: fixed; top: 0; left: 0; right: 0; z-index: 2147483647;
           font: 14px/1.4 system-ui, sans-serif; color: #fff; padding: 10px 16px;
           box-shadow: 0 2px 8px rgba(0,0,0,.3); }
    .bar.phishing { background: #c62828; }
    .bar.suspicious { background: #ef6c00; }
    ul { margin: 6px 0 0 18px; padding: 0; }
    button { position: absolute; top: 8px; right: 12px; cursor: pointer;
             border: 1px solid #fff; background: transparent; color: #fff;
             border-radius: 4px; padding: 2px 10px; }
  `;

  const bar = document.createElement("div");
  bar.className = `bar ${result.verdict}`;

  const title = document.createElement("strong");
  title.textContent =
    result.verdict === "phishing"
      ? "⚠ Cảnh báo: trang này có dấu hiệu lừa đảo (phishing)"
      : "⚠ Trang này có dấu hiệu đáng ngờ";

  const list = document.createElement("ul");
  for (const reason of result.reasons) {
    const li = document.createElement("li");
    li.textContent = reason;
    list.append(li);
  }

  const close = document.createElement("button");
  close.textContent = "Đóng";
  close.addEventListener("click", () => host.remove());

  bar.append(title, list, close);
  root.append(style, bar);
  document.documentElement.append(host);
}

chrome.runtime.onMessage.addListener((msg: ExtMessage) => {
  if (msg.type === "SHOW_WARNING") showBanner(msg.result);
});

// Gửi thông tin trang cho background ngay khi tải xong.
const message: ExtMessage = { type: "PAGE_INFO", payload: collectPageInfo() };
chrome.runtime.sendMessage(message).catch(() => {
  /* service worker có thể chưa sẵn sàng; bỏ qua ở bản đầu */
});

// ---------- Rê chuột vào link: cảnh báo trước khi bấm ----------
// Chấm bằng bộ luật cục bộ (không gửi gì lên máy chủ) nên nhanh và riêng tư.
const TIP_ID = "phishguard-link-tip";
let hoverTimer: number | undefined;

function hideTip(): void {
  document.getElementById(TIP_ID)?.remove();
}

async function showLinkTip(a: HTMLAnchorElement): Promise<void> {
  let u: URL;
  try {
    u = new URL(a.href);
  } catch {
    return;
  }
  if (!/^https?:$/.test(u.protocol) || u.hostname === location.hostname) return;
  const r = await analyzeLocal({ url: u.href, hostname: u.hostname, protocol: u.protocol, hasPasswordField: false });
  if (r.verdict === "safe") return;

  hideTip();
  const host = document.createElement("div");
  host.id = TIP_ID;
  const root = host.attachShadow({ mode: "open" });
  const rect = a.getBoundingClientRect();
  const style = document.createElement("style");
  style.textContent = `
    .tip { position: fixed; z-index: 2147483647; max-width: 360px; padding: 8px 12px;
           border-radius: 8px; color: #fff; font: 13px/1.4 system-ui, sans-serif;
           box-shadow: 0 4px 14px rgba(0,0,0,.3); pointer-events: none; }
    .phishing { background: #c62828; } .suspicious { background: #ef6c00; }
    .host { font-family: ui-monospace, Consolas, monospace; word-break: break-all; }
  `;
  const tip = document.createElement("div");
  tip.className = `tip ${r.verdict}`;
  tip.style.left = `${Math.max(8, Math.min(rect.left, innerWidth - 370))}px`;
  tip.style.top = rect.bottom + 70 < innerHeight ? `${rect.bottom + 6}px` : `${Math.max(8, rect.top - 70)}px`;
  const title = document.createElement("strong");
  title.textContent = r.verdict === "phishing" ? "⚠ Link có dấu hiệu lừa đảo" : "⚠ Link đáng ngờ";
  const hostEl = document.createElement("div");
  hostEl.className = "host";
  hostEl.textContent = u.hostname;
  const why = document.createElement("div");
  why.textContent = r.reasons[0] ?? "";
  tip.append(title, hostEl, why);
  root.append(style, tip);
  document.documentElement.append(host);
}

document.addEventListener("mouseover", (e) => {
  const a = (e.target as Element | null)?.closest?.("a[href]") as HTMLAnchorElement | null;
  clearTimeout(hoverTimer);
  if (!a) return;
  hoverTimer = window.setTimeout(() => void showLinkTip(a), 250);
});
document.addEventListener("mouseout", (e) => {
  if ((e.target as Element | null)?.closest?.("a[href]")) {
    clearTimeout(hoverTimer);
    hideTip();
  }
});
document.addEventListener("scroll", hideTip, { passive: true });
