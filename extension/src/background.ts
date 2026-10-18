import { allowOnce, applyAdRules } from "./adblock";
import { analyze, analyzeEmail, analyzeUrl, sendReport } from "./analyzer";
import type { AnalysisResult, ExtMessage, PageInfo } from "./types";

const resultKey = (tabId: number) => `result:${tabId}`;

async function handlePageInfo(tabId: number, info: PageInfo): Promise<void> {
  const result = await analyze(info);
  await chrome.storage.session.set({ [resultKey(tabId)]: result });

  const flagged = result.verdict !== "safe";
  await chrome.action.setBadgeText({ tabId, text: flagged ? "!" : "" });
  if (flagged) {
    await chrome.action.setBadgeBackgroundColor({
      tabId,
      color: result.verdict === "phishing" ? "#c62828" : "#ef6c00",
    });
    chrome.tabs.sendMessage(tabId, { type: "SHOW_WARNING", result } satisfies ExtMessage).catch(() => {});
  }
}

chrome.runtime.onMessage.addListener((msg: ExtMessage, sender, sendResponse) => {
  if (msg.type === "PAGE_INFO" && sender.tab?.id !== undefined) {
    void handlePageInfo(sender.tab.id, msg.payload);
    return false;
  }
  // Các yêu cầu dưới đây gọi API từ background (content script trên Gmail bị
  // CSP của trang chặn gọi thẳng tới backend).
  if (msg.type === "ANALYZE_EMAIL") {
    analyzeEmail(msg.payload).then(sendResponse);
    return true;
  }
  if (msg.type === "ANALYZE_URL") {
    analyzeUrl(msg.url, msg.kind).then(sendResponse);
    return true;
  }
  if (msg.type === "AD_ALLOW") {
    allowOnce(msg.url).then(sendResponse);
    return true;
  }
  if (msg.type === "REPORT") {
    sendReport(msg.payload).then(sendResponse);
    return true;
  }
  if (msg.type === "GET_RESULT") {
    chrome.storage.session.get(resultKey(msg.tabId)).then((data) => {
      sendResponse((data[resultKey(msg.tabId)] as AnalysisResult | undefined) ?? null);
    });
    return true; // giữ kênh mở cho phản hồi bất đồng bộ
  }
  return false;
});

chrome.tabs.onRemoved.addListener((tabId) => {
  void chrome.storage.session.remove(resultKey(tabId));
});

// Luật chặn quảng cáo: cài khi cài/cập nhật extension, khi mở Chrome, và khi
// người dùng bật/tắt trong popup.
chrome.runtime.onInstalled.addListener(() => void applyAdRules());
chrome.runtime.onStartup.addListener(() => void applyAdRules());
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "local" && "adBlock" in changes) void applyAdRules();
});
