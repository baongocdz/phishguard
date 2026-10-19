// Chặn chuyển hướng tới mạng quảng cáo popunder/chuyển hướng cưỡng ép bằng
// declarativeNetRequest: Chrome tự đổi hướng sang blocked.html trước khi tải
// trang quảng cáo, nên không cần đọc nội dung trang nào.
import adList from "./ad-domains.json";

export const AD_DOMAINS: string[] = adList.domains;
// Link tiếp thị liên kết (affiliate). Trên các trang phim/truyện lậu ở Việt Nam,
// "bấm đâu cũng chuyển trang" thường dẫn tới đây (học từ bộ lọc ABPVN).
export const AFFILIATE_DOMAINS: string[] = adList.affiliate;
const AFFILIATE_HOME: string[] = adList.affiliateHome;

const RULE_AD = 1000;
const RULE_AD_FRAME = 1001;
const RULE_AFFILIATE = 1002;
const RULE_POP_MARKER = 1003;
// Trang đích của quảng cáo popunder thường tự khai trong URL (vd yo88.town/?utm_medium=popunder).
// Bắt được cả khi mạng quảng cáo không có trong danh sách. \0 = toàn bộ URL.
const POP_MARKER = "^https?://.*[?&]utm_medium=(popunder|popup|pop|onclick|clickunder|tabunder)([&#].*)?$";
const ALLOW_BASE = 2000; // 2000.. luật "luôn cho phép" người dùng đã chọn
const ONCE_BASE = 9000; // 9000.. luật "cho qua một lần" (session, 60 giây)

// Chrome giới hạn mỗi regex 2KB bộ nhớ, nên KHÔNG so tên miền bằng regex.
// requestDomains lo phần so tên miền (khớp cả tên miền con); regex "^.+$" chỉ để
// lấy lại toàn bộ URL (\0) gắn vào sau dấu # của trang cảnh báo.
/** Trang cảnh báo của extension cho URL bị chặn; prefix: ad | aff | pop. */
export function blockedPage(prefix: string, url: string): string {
  return `${chrome.runtime.getURL("blocked.html")}#${prefix}|${url}`;
}

function redirectTo(prefix: string): chrome.declarativeNetRequest.RuleAction {
  return {
    type: chrome.declarativeNetRequest.RuleActionType.REDIRECT,
    redirect: { regexSubstitution: `${chrome.runtime.getURL("blocked.html")}#${prefix}\\0` },
  };
}

function buildRules(allowed: string[]): chrome.declarativeNetRequest.Rule[] {
  const MAIN = chrome.declarativeNetRequest.ResourceType.MAIN_FRAME;
  const rules: chrome.declarativeNetRequest.Rule[] = [
    {
      id: RULE_AD,
      priority: 1,
      action: redirectTo("ad|"),
      condition: { regexFilter: "^.+$", requestDomains: AD_DOMAINS, resourceTypes: [MAIN] },
    },
    {
      // Khung quảng cáo nhúng trong trang (iframe) thì chặn thẳng.
      id: RULE_AD_FRAME,
      priority: 1,
      action: { type: chrome.declarativeNetRequest.RuleActionType.BLOCK },
      condition: { requestDomains: AD_DOMAINS, resourceTypes: [chrome.declarativeNetRequest.ResourceType.SUB_FRAME] },
    },
    {
      // Chỉ cảnh báo khi trang BÊN THỨ BA đẩy sang link affiliate; đang ở chính
      // Shopee/Lazada thì không.
      id: RULE_AFFILIATE,
      priority: 1,
      action: redirectTo("aff|"),
      condition: {
        regexFilter: "^.+$",
        requestDomains: AFFILIATE_DOMAINS,
        excludedInitiatorDomains: AFFILIATE_HOME,
        resourceTypes: [MAIN],
      },
    },
    {
      id: RULE_POP_MARKER,
      priority: 1,
      action: redirectTo("pop|"),
      condition: { regexFilter: POP_MARKER, isUrlFilterCaseSensitive: false, resourceTypes: [MAIN] },
    },
  ];
  allowed.slice(0, 500).forEach((domain, i) => rules.push({
    id: ALLOW_BASE + i,
    priority: 2,
    action: { type: chrome.declarativeNetRequest.RuleActionType.ALLOW },
    condition: { requestDomains: [domain], resourceTypes: [MAIN] },
  }));
  return rules;
}

export async function applyAdRules(): Promise<void> {
  const { adBlock, adAllow } = await chrome.storage.local.get(["adBlock", "adAllow"]);
  const existing = await chrome.declarativeNetRequest.getDynamicRules();
  await chrome.declarativeNetRequest.updateDynamicRules({
    removeRuleIds: existing.filter((r) => r.id >= RULE_AD && r.id < ONCE_BASE).map((r) => r.id),
    addRules: adBlock === false ? [] : buildRules(Array.isArray(adAllow) ? adAllow : []), // mặc định bật
  });
}

function hostOf(url: string): string | null {
  try {
    return new URL(url).hostname;
  } catch {
    return null;
  }
}

/** "Vẫn mở": cho tên miền này qua trong 60 giây. */
export async function allowOnce(url: string): Promise<boolean> {
  const host = hostOf(url);
  if (!host) return false;
  const id = ONCE_BASE + Math.floor(Math.random() * 900);
  await chrome.declarativeNetRequest.updateSessionRules({
    removeRuleIds: [id],
    addRules: [{
      id,
      priority: 3,
      action: { type: chrome.declarativeNetRequest.RuleActionType.ALLOW },
      condition: { requestDomains: [host], resourceTypes: [chrome.declarativeNetRequest.ResourceType.MAIN_FRAME] },
    }],
  });
  setTimeout(() => void chrome.declarativeNetRequest.updateSessionRules({ removeRuleIds: [id] }), 60_000);
  return true;
}

/** "Luôn cho phép tên miền này": nhớ vĩnh viễn (xóa được trong popup). */
export async function allowAlways(url: string): Promise<boolean> {
  const host = hostOf(url);
  if (!host) return false;
  const { adAllow } = await chrome.storage.local.get("adAllow");
  const list: string[] = Array.isArray(adAllow) ? adAllow : [];
  if (!list.includes(host)) list.push(host);
  await chrome.storage.local.set({ adAllow: list });
  await applyAdRules();
  return true;
}
