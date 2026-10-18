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

  return {
    url: location.href,
    hostname: location.hostname,
    protocol: location.protocol,
    title: document.title,
    formCount: document.forms.length,
    hasPasswordField: document.querySelector("input[type='password']") !== null,
    linkCount: links.length,
    externalLinkCount,
    collectedAt: Date.now(),
  };
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
