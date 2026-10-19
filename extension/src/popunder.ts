// Phát hiện tab quảng cáo tự bật (popunder) KHÔNG cần danh sách mạng quảng cáo.
//
// Trang tự mở tab mới sang một trang web KHÁC ngay sau cú bấm của người dùng, mà chỗ được
// bấm không phải là link tới trang đó (nút Play, nền trang, link trong suốt phủ kín màn hình)
// → đó là quảng cáo. Tab mới được đổi sang trang cảnh báo (có "Mở lần này" / "Luôn cho phép").
// Danh sách trong ad-domains.json vẫn chặn trước được các mạng đã biết; phần này bắt mạng lạ.
import { AD_DOMAINS, AFFILIATE_DOMAINS, blockedPage } from "./adblock";
import { isOfficialBrandHost } from "./analyzer";
import type { ClickInfo, ExtMessage } from "./types";

// Cửa sổ đăng nhập / thanh toán / chia sẻ hay được mở bằng script: không bao giờ chặn.
const TRUSTED_POPUP_SITES = [
  "appleid.apple.com", "login.microsoftonline.com", "login.live.com", "github.com", "id.zalo.me",
  "twitter.com", "x.com", "linkedin.com", "pinterest.com", "reddit.com", "t.me", "telegram.org",
  "youtube.com", "tiktok.com", "discord.com", "stripe.com", "vnpay.vn", "zalopay.vn", "napas.com.vn",
];
const CLICK_WINDOW_MS = 5000; // Chrome chỉ cho trang mở tab mới trong vài giây sau cú bấm
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

/** Quyết định tab mới (mở từ sourceUrl, tới targetUrl) có phải popunder không. Hàm thuần, để test. */
export function isPopunder(sourceUrl: string, targetUrl: string, click: ClickInfo | null, allowed: string[], now = Date.now()): boolean {
  const target = hostOf(targetUrl);
  const source = hostOf(sourceUrl);
  if (!/^https?:/i.test(targetUrl) || !target || !source) return false;
  if (siteOf(target) === siteOf(source)) return false; // mở trang cùng web: bình thường
  if (matches(target, [...AD_DOMAINS, ...AFFILIATE_DOMAINS])) return false; // luật danh sách đã lo
  if (isOfficialBrandHost(target) || matches(target, TRUSTED_POPUP_SITES)) return false;
  if (matches(target, allowed) || matches(source, allowed)) return false; // người dùng đã cho phép
  if (!click || now - click.at > CLICK_WINDOW_MS) return false; // không biết cú bấm: không đoán bừa
  const linkHost = hostOf(click.href);
  if (linkHost && !click.overlay && siteOf(linkHost) === siteOf(target)) return false; // bấm đúng link đó
  return true;
}

// Tab mới mở bằng window.open() thường bắt đầu ở about:blank rồi script mới gán địa chỉ:
// nhớ lại vài giây để xét ở lần điều hướng đầu tiên.
const pending = new Map<number, { sourceTabId: number; sourceFrameId: number; until: number }>();

async function check(tabId: number, sourceTabId: number, sourceFrameId: number, targetUrl: string): Promise<void> {
  const { adBlock, adAllow } = await chrome.storage.local.get(["adBlock", "adAllow"]);
  if (adBlock === false) return;
  const [top, click] = await Promise.all([
    chrome.webNavigation.getFrame({ tabId: sourceTabId, frameId: 0 }).catch(() => null),
    chrome.tabs.sendMessage(sourceTabId, { type: "LAST_CLICK" } satisfies ExtMessage, { frameId: sourceFrameId })
      .catch(() => null) as Promise<ClickInfo | null>,
  ]);
  if (!top?.url) return;
  // Cửa sổ nhỏ kiểu đăng nhập (window.open có kích thước) là "popup", không phải tab quảng cáo.
  const win = await chrome.tabs.get(tabId).then((t) => chrome.windows.get(t.windowId)).catch(() => null);
  if (win?.type === "popup") return;
  if (isPopunder(top.url, targetUrl, click, Array.isArray(adAllow) ? adAllow : [])) {
    await chrome.tabs.update(tabId, { url: blockedPage("pop", targetUrl) }).catch(() => {});
  }
}

export function watchPopunders(): void {
  chrome.webNavigation.onCreatedNavigationTarget.addListener((d) => {
    if (/^https?:/i.test(d.url)) void check(d.tabId, d.sourceTabId, d.sourceFrameId, d.url);
    else pending.set(d.tabId, { sourceTabId: d.sourceTabId, sourceFrameId: d.sourceFrameId, until: Date.now() + 3000 });
  });
  chrome.webNavigation.onBeforeNavigate.addListener((d) => {
    const p = pending.get(d.tabId);
    if (!p || d.frameId !== 0 || !/^https?:/i.test(d.url)) return;
    pending.delete(d.tabId);
    if (Date.now() <= p.until) void check(d.tabId, p.sourceTabId, p.sourceFrameId, d.url);
  });
  chrome.tabs.onRemoved.addListener((tabId) => pending.delete(tabId));
}
