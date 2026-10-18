// Chặn chuyển hướng tới mạng quảng cáo popunder/chuyển hướng cưỡng ép bằng
// declarativeNetRequest: Chrome tự đổi hướng sang blocked.html trước khi tải
// trang quảng cáo, nên không cần đọc nội dung trang nào.
import adList from "./ad-domains.json";

export const AD_DOMAINS: string[] = adList.domains;

const BASE_ID = 1000; // id 1000.. cho luật chặn, 9000.. cho luật "cho qua một lần"
const CHUNK = 10; // tách regex cho gọn, tránh vượt giới hạn bộ nhớ regex của Chrome

const escape = (d: string) => d.replace(/[.*+?^${}()|[\]\\-]/g, "\\$&");

function buildRules(): chrome.declarativeNetRequest.Rule[] {
  const page = chrome.runtime.getURL("blocked.html");
  const rules: chrome.declarativeNetRequest.Rule[] = [];
  for (let i = 0; i < AD_DOMAINS.length; i += CHUNK) {
    const group = AD_DOMAINS.slice(i, i + CHUNK).map(escape).join("|");
    rules.push({
      id: BASE_ID + rules.length,
      priority: 1,
      action: {
        type: chrome.declarativeNetRequest.RuleActionType.REDIRECT,
        // \0 = toàn bộ URL gốc, đặt sau dấu # để trang cảnh báo đọc lại.
        redirect: { regexSubstitution: `${page}#\\0` },
      },
      condition: {
        regexFilter: `^https?://([^/?#]*\\.)?(${group})([/?#:].*)?$`,
        resourceTypes: [chrome.declarativeNetRequest.ResourceType.MAIN_FRAME],
      },
    });
  }
  // Khung quảng cáo nhúng trong trang (iframe) thì chặn thẳng.
  rules.push({
    id: BASE_ID + rules.length,
    priority: 1,
    action: { type: chrome.declarativeNetRequest.RuleActionType.BLOCK },
    condition: {
      requestDomains: AD_DOMAINS,
      resourceTypes: [chrome.declarativeNetRequest.ResourceType.SUB_FRAME],
    },
  });
  return rules;
}

export async function applyAdRules(): Promise<void> {
  const { adBlock } = await chrome.storage.local.get("adBlock");
  const existing = await chrome.declarativeNetRequest.getDynamicRules();
  await chrome.declarativeNetRequest.updateDynamicRules({
    removeRuleIds: existing.filter((r) => r.id >= BASE_ID && r.id < 9000).map((r) => r.id),
    addRules: adBlock === false ? [] : buildRules(), // mặc định bật
  });
}

/** Người dùng bấm "Vẫn mở": cho tên miền này qua trong 60 giây. */
export async function allowOnce(url: string): Promise<boolean> {
  let host: string;
  try {
    host = new URL(url).hostname;
  } catch {
    return false;
  }
  const id = 9000 + Math.floor(Math.random() * 900);
  await chrome.declarativeNetRequest.updateSessionRules({
    removeRuleIds: [id],
    addRules: [{
      id,
      priority: 2,
      action: { type: chrome.declarativeNetRequest.RuleActionType.ALLOW },
      condition: { requestDomains: [host], resourceTypes: [chrome.declarativeNetRequest.ResourceType.MAIN_FRAME] },
    }],
  });
  setTimeout(() => void chrome.declarativeNetRequest.updateSessionRules({ removeRuleIds: [id] }), 60_000);
  return true;
}
