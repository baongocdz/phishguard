// Phát hiện quảng cáo tự bật KHÔNG cần danh sách mạng quảng cáo:
//
// - Popunder: trang tự mở tab/cửa sổ mới sang một trang web KHÁC ngay sau cú bấm của người dùng.
// - Tab-under: chính tab đang xem tự chuyển sang một trang web KHÁC ngay sau cú bấm (phim thì mở ở tab mới).
//
// Nếu chỗ được bấm không phải là link tới trang đó (nút Play, nền trang, link trong suốt phủ kín màn
// hình) thì đó là quảng cáo → đổi sang trang cảnh báo (có "Mở lần này" / "Luôn cho phép").
// Danh sách trong ad-domains.json vẫn chặn trước được các mạng đã biết; phần này bắt mạng lạ.
import { AD_DOMAINS, AFFILIATE_DOMAINS, blockedPage } from "./adblock";
import { isTrustedHost } from "./analyzer";
import type { ClickInfo } from "./types";

// Cửa sổ đăng nhập / thanh toán / chia sẻ hay được mở bằng script: không bao giờ chặn.
const TRUSTED_POPUP_SITES = [
  "appleid.apple.com", "login.microsoftonline.com", "login.live.com", "github.com", "id.zalo.me",
  "twitter.com", "x.com", "linkedin.com", "pinterest.com", "reddit.com", "t.me", "telegram.org",
  "youtube.com", "tiktok.com", "discord.com", "stripe.com", "vnpay.vn", "zalopay.vn", "napas.com.vn",
];
// Cửa sổ nhỏ (window.open có kích thước) chỉ được miễn khi trông như đăng nhập / ủy quyền / thanh toán;
// popunder cổ điển cũng dùng cửa sổ nhỏ nên không miễn hết.
const AUTH_PATH = /\/(oauth2?|authorize|auth|login|signin|sign-in|sso|connect|checkout|pay(ment)?)\b/i;
const NEW_TAB_WINDOW_MS = 5000; // Chrome chỉ cho trang mở tab mới trong vài giây sau cú bấm
const SAME_TAB_WINDOW_MS = 8000; // tính tới lúc trang quảng cáo trả lời (cú bấm cũ đã bị xóa khi tab sang trang)
// Đuôi hai cấp hay gặp: abc.com.vn và xyz.com.vn là hai trang khác nhau.
const TWO_LEVEL = /\.(com|net|org|edu|gov|ac|co|info|biz|name|pro|int|health)\.[a-z]{2}$/;

function hostOf(url: string): string {
  try {
    return new URL(url).hostname.toLowerCase();
  } catch {
    return "";
  }
}

/** "Trang web" (tên miền đăng ký): m.phim.com và phim.com là một trang. */
export function siteOf(host: string): string {
  if (/^[\d.]+$/.test(host) || !host.includes(".")) return host; // IP, localhost
  const parts = host.split(".");
  return parts.slice(TWO_LEVEL.test(host) ? -3 : -2).join(".");
}

function matches(host: string, domains: string[]): boolean {
  return domains.some((d) => host === d || host.endsWith("." + d));
}

/** Trang (sourceUrl) đẩy người dùng sang targetUrl ngay sau cú bấm `click`: có phải quảng cáo không. Hàm thuần. */
export function isPopunder(sourceUrl: string, targetUrl: string, click: ClickInfo | null, allowed: string[],
  windowMs = NEW_TAB_WINDOW_MS, now = Date.now()): boolean {
  const target = hostOf(targetUrl);
  const source = hostOf(sourceUrl);
  if (!/^https?:/i.test(targetUrl) || !/^https?:/i.test(sourceUrl) || !target || !source) return false;
  if (siteOf(target) === siteOf(source)) return false; // sang trang cùng web: bình thường
  if (matches(target, [...AD_DOMAINS, ...AFFILIATE_DOMAINS])) return false; // luật danh sách đã lo
  if (isTrustedHost(target) || matches(target, TRUSTED_POPUP_SITES)) return false; // không miễn sites.google.com...
  if (matches(target, allowed) || matches(source, allowed)) return false; // người dùng đã cho phép
  if (!click || now - click.at > windowMs) return false; // không có cú bấm gần đây: không đoán bừa
  if (click.formSubmit) return false; // gửi form sang trang khác (thanh toán, đăng nhập) là bình thường
  const linkHost = hostOf(click.href);
  if (linkHost && !click.overlay && siteOf(linkHost) === siteOf(target)) return false; // bấm đúng link đó
  return true;
}

// Cú bấm gần nhất của từng tab (clicktrack.ts gửi lên, từ mọi khung kể cả iframe trình phát phim).
const lastClick = new Map<number, ClickInfo>();
export function recordClick(tabId: number, click: ClickInfo): void {
  lastClick.set(tabId, click);
}

// Tab mới mở bằng window.open() thường bắt đầu ở about:blank rồi script mới gán địa chỉ:
// nhớ lại vài giây để xét ở lần điều hướng đầu tiên.
const pending = new Map<number, { sourceTabId: number; until: number }>();
const newTabs = new Set<number>();

async function settings(): Promise<{ on: boolean; allowed: string[] }> {
  const { adBlock, adAllow } = await chrome.storage.local.get(["adBlock", "adAllow"]);
  return { on: adBlock !== false, allowed: Array.isArray(adAllow) ? adAllow : [] };
}

async function checkNewTab(tabId: number, sourceTabId: number, targetUrl: string): Promise<void> {
  const { on, allowed } = await settings();
  if (!on) return;
  await new Promise((r) => setTimeout(r, 150)); // chờ tin nhắn cú bấm (gửi lúc pointerdown) tới nơi
  const top = await chrome.webNavigation.getFrame({ tabId: sourceTabId, frameId: 0 }).catch(() => null);
  if (!top?.url) return;
  // Cửa sổ nhỏ kiểu đăng nhập / thanh toán: cho qua. Cửa sổ nhỏ tới trang thường: vẫn xét (popunder cổ điển).
  const win = await chrome.tabs.get(tabId).then((t) => chrome.windows.get(t.windowId)).catch(() => null);
  if (win?.type === "popup" && AUTH_PATH.test(new URL(targetUrl).pathname)) return;
  if (isPopunder(top.url, targetUrl, lastClick.get(sourceTabId) ?? null, allowed)) {
    await chrome.tabs.update(tabId, { url: blockedPage("pop", targetUrl) }).catch(() => {});
  }
}

/** Tab-under: chính tab đang xem tự chuyển sang web khác ngay sau cú bấm không phải vào link tới đó. */
async function checkSameTab(tabId: number, fromUrl: string, targetUrl: string, shownUrl: string, click: ClickInfo): Promise<void> {
  const { on, allowed } = await settings();
  if (!on || !isPopunder(fromUrl, targetUrl, click, allowed, SAME_TAB_WINDOW_MS)) return;
  await chrome.tabs.update(tabId, { url: blockedPage("tu", shownUrl) }).catch(() => {});
}

// Địa chỉ đã mở của từng tab, và địa chỉ BAN ĐẦU của lần điều hướng đang diễn ra (trước chuyển hướng phía
// server: bấm link bit.ly rồi server chuyển sang trang khác thì vẫn là "bấm đúng link").
const lastUrl = new Map<number, string>();
const startUrl = new Map<number, string>();
// Địa chỉ trang đang mở lúc điều hướng BẮT ĐẦU, hỏi thẳng Chrome. Không chỉ dựa vào lastUrl: service worker bị Chrome
// tắt sau ~30 giây rảnh (mất hết biến trong bộ nhớ) → xem phim quá 30 giây rồi mới bấm Play thì lastUrl đã mất.
const fromUrl = new Map<number, string>();

export function watchPopunders(): void {
  chrome.webNavigation.onCreatedNavigationTarget.addListener((d) => {
    newTabs.add(d.tabId);
    if (/^https?:/i.test(d.url)) void checkNewTab(d.tabId, d.sourceTabId, d.url);
    else pending.set(d.tabId, { sourceTabId: d.sourceTabId, until: Date.now() + 3000 });
  });
  chrome.webNavigation.onBeforeNavigate.addListener((d) => {
    if (d.frameId !== 0 || !/^https?:/i.test(d.url)) return;
    const p = pending.get(d.tabId);
    if (p) {
      pending.delete(d.tabId);
      if (Date.now() <= p.until) void checkNewTab(d.tabId, p.sourceTabId, d.url);
      return;
    }
    startUrl.set(d.tabId, d.url);
    const tabId = d.tabId;
    void chrome.webNavigation.getFrame({ tabId, frameId: 0 }).then((f) => {
      if (f?.url) fromUrl.set(tabId, f.url);
    }).catch(() => {});
  });
  // Xét tab-under lúc trang mới được xác nhận: lúc này Chrome cho biết LOẠI điều hướng (link/script, gõ địa
  // chỉ, bookmark, Back…) — lúc bắt đầu thì chưa, nên gõ địa chỉ ngay sau khi bấm nút sẽ bị bắt nhầm.
  chrome.webNavigation.onCommitted.addListener((d) => {
    if (d.frameId !== 0) return;
    const from = fromUrl.get(d.tabId) ?? lastUrl.get(d.tabId);
    const start = startUrl.get(d.tabId) ?? d.url;
    const click = lastClick.get(d.tabId);
    const wasNew = newTabs.delete(d.tabId);
    lastUrl.set(d.tabId, d.url);
    startUrl.delete(d.tabId);
    fromUrl.delete(d.tabId);
    // Cú bấm đã "dùng xong" khi tab sang trang mới: bấm link rồi bấm Back ngay không bị coi là tab-under.
    lastClick.delete(d.tabId);
    const q = d.transitionQualifiers;
    if (wasNew || !from || !click || d.transitionType !== "link" || q.includes("forward_back") || q.includes("from_address_bar")) return;
    void checkSameTab(d.tabId, from, start, d.url, click);
  });
  chrome.tabs.onRemoved.addListener((tabId) => {
    pending.delete(tabId);
    newTabs.delete(tabId);
    lastClick.delete(tabId);
    lastUrl.delete(tabId);
    startUrl.delete(tabId);
    fromUrl.delete(tabId);
  });
}
