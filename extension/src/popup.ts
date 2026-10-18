import type { AnalysisResult, ExtMessage } from "./types";

const LABEL = { safe: "An toàn", suspicious: "Đáng ngờ", phishing: "Phishing" } as const;

async function main(): Promise<void> {
  const urlEl = document.getElementById("url");
  const verdictEl = document.getElementById("verdict");
  const reasonsEl = document.getElementById("reasons");

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (urlEl) {
    urlEl.textContent = tab?.url ?? "";
  }

  const result: AnalysisResult | null = tab?.id
    ? await chrome.runtime.sendMessage({ type: "GET_RESULT", tabId: tab.id } satisfies ExtMessage)
    : null;

  if (!result) {
    if (verdictEl) {
      verdictEl.className = "chip none";
      verdictEl.textContent = "Chưa có dữ liệu (thử tải lại trang)";
    }
    return;
  }

  if (verdictEl) {
    verdictEl.className = `chip ${result.verdict}`;
    verdictEl.textContent = `${LABEL[result.verdict]} · điểm ${result.score}`;
  }

  if (reasonsEl) {
    reasonsEl.innerHTML = "";
    for (const reason of result.reasons) {
      const li = document.createElement("li");
      li.textContent = reason;
      reasonsEl.append(li);
    }
  }

  // Tự động tìm thẻ source; nếu chưa có trong HTML thì code tự tạo mới và gắn vào cuối body
  let sourceEl = document.getElementById("source");
  if (!sourceEl) {
    sourceEl = document.createElement("p");
    sourceEl.id = "source";
    sourceEl.className = "url";
    document.body.appendChild(sourceEl);
  }
  sourceEl.textContent = `Nguồn kết quả: ${result.source}`;
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    void main();
  });
} else {
  void main();
}