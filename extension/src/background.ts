import { allowAlways, allowOnce, applyAdRules } from "./adblock";
import { analyze, analyzeEmail, analyzeUrl, sendReport } from "./analyzer";
import { recordClick, watchPopunders } from "./popunder";
import type { AnalysisResult, EmailInfo, EmailResult, ExtMessage, HistoryItem, PageInfo } from "./types";

const resultKey = (tabId: number) => `result:${tabId}`;
const emailKey = (tabId: number) => `email:${tabId}`;
const HISTORY_MAX = 30;

/** Lịch sử cảnh báo: chỉ lưu trên máy (chrome.storage.local), tối đa HISTORY_MAX dòng. */
export async function addHistory(item: HistoryItem): Promise<void> {
  const { history } = await chrome.storage.local.get("history");
  const list: HistoryItem[] = Array.isArray(history) ? history : [];
  const fresh = list.filter((h) => h.url !== item.url); // trang mở lại thì đưa lên đầu
  await chrome.storage.local.set({ history: [item, ...fresh].slice(0, HISTORY_MAX) });
}

async function handlePageInfo(tabId: number, info: PageInfo): Promise<void> {
  const result = { ...(await analyze(info)), url: info.url };
  await chrome.storage.session.set({ [resultKey(tabId)]: result });

  const flagged = result.verdict !== "safe";
  if (flagged) await addHistory({ url: info.url, verdict: result.verdict, score: result.score, kind: "page", at: Date.now() });
  await chrome.action.setBadgeText({ tabId, text: flagged ? "!" : "" });
  if (flagged) {
    await chrome.action.setBadgeBackgroundColor({
      tabId,
      color: result.verdict === "phishing" ? "#c62828" : "#ef6c00",
    });
    chrome.tabs.sendMessage(tabId, { type: "SHOW_WARNING", result } satisfies ExtMessage).catch(() => {});
  }
}

/** Email đang mở trong Gmail: phân tích, nhớ theo tab để popup hiện lại, email nguy hiểm thì ghi lịch sử. */
async function handleEmail(email: EmailInfo, tabId: number | undefined, url: string): Promise<AnalysisResult | null> {
  const result = await analyzeEmail(email);
  if (result && tabId !== undefined) {
    const stored: EmailResult = { url, subject: email.subject, sender: email.sender, result };
    await chrome.storage.session.set({ [emailKey(tabId)]: stored });
    if (result.verdict !== "safe") {
      await addHistory({ url: email.subject || email.sender, verdict: result.verdict, score: result.score, kind: "email", at: Date.now() });
    }
  }
  return result;
}

chrome.runtime.onMessage.addListener((msg: ExtMessage, sender, sendResponse) => {
  if (msg.type === "CLICK" && sender.tab?.id !== undefined) {
    recordClick(sender.tab.id, msg.click);
    return false;
  }
  if (msg.type === "PAGE_INFO" && sender.tab?.id !== undefined) {
    void handlePageInfo(sender.tab.id, msg.payload);
    return false;
  }
  // Các yêu cầu dưới đây gọi API từ background (content script trên Gmail bị
  // CSP của trang chặn gọi thẳng tới backend).
  if (msg.type === "ANALYZE_EMAIL") {
    handleEmail(msg.payload, sender.tab?.id, msg.pageUrl ?? sender.url ?? "").then(sendResponse);
    return true;
  }
  if (msg.type === "GET_EMAIL_RESULT") {
    chrome.storage.session.get(emailKey(msg.tabId)).then((data) => {
      sendResponse((data[emailKey(msg.tabId)] as EmailResult | undefined) ?? null);
    });
    return true;
  }
  if (msg.type === "ANALYZE_URL") {
    analyzeUrl(msg.url, msg.kind).then(async (r) => {
      if (r && r.verdict !== "safe" && msg.kind === "qr") {
        await addHistory({ url: msg.url, verdict: r.verdict, score: r.score, kind: "qr", at: Date.now() });
      }
      sendResponse(r);
    });
    return true;
  }
  if (msg.type === "AD_ALLOW") {
    (msg.always ? allowAlways(msg.url) : allowOnce(msg.url)).then(sendResponse);
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
  void chrome.storage.session.remove([resultKey(tabId), emailKey(tabId)]);
});

watchPopunders();

// Luật chặn quảng cáo: cài khi cài/cập nhật extension, khi mở Chrome, và khi
// người dùng bật/tắt trong popup.
chrome.runtime.onInstalled.addListener(() => void applyAdRules());
chrome.runtime.onStartup.addListener(() => void applyAdRules());
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "local" && ("adBlock" in changes || "adAllow" in changes)) void applyAdRules();
});
