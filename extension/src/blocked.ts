import type { ExtMessage } from "./types";

// Hash có dạng "ad|<url>" hoặc "aff|<url>" (xem adblock.ts).
function readHash(): { kind: "ad" | "aff"; url: string } {
  let raw = location.hash.slice(1);
  try {
    raw = decodeURIComponent(raw);
  } catch {
    // URL có ký tự % lạ: dùng nguyên văn
  }
  const sep = raw.indexOf("|");
  const prefix = sep > 0 ? raw.slice(0, sep) : "";
  if (prefix === "ad" || prefix === "aff") return { kind: prefix, url: raw.slice(sep + 1) };
  return { kind: "ad", url: raw };
}

const { kind, url: target } = readHash();
const $ = (id: string) => document.getElementById(id)!;
$("url").textContent = target || "(không rõ)";

if (kind === "aff") {
  document.title = "PhishGuard: trang vừa ép mở link tiếp thị liên kết";
  $("title").textContent = "🛍️ Trang vừa ép mở link tiếp thị liên kết";
  $("lead").textContent = "Trang bạn đang xem vừa tự đưa bạn sang một link tiếp thị liên kết (affiliate) của sàn thương mại điện tử:";
  $("tip1").textContent = "Các trang phim/truyện lậu hay làm vậy để nhận hoa hồng mỗi khi bạn mua hàng, dù bạn không hề bấm vào quảng cáo.";
  $("tip2").textContent = "Link này thường không độc hại. Nếu bạn chủ động bấm vào thì có thể mở tiếp.";
}

// Đếm số lần chặn để hiện trong popup.
chrome.storage.local.get("adBlockedCount").then(({ adBlockedCount }) =>
  chrome.storage.local.set({ adBlockedCount: (Number(adBlockedCount) || 0) + 1 }));

$("back").addEventListener("click", () => {
  // Tab mới do popunder mở ra thì không có trang trước: đóng luôn.
  if (history.length > 1) history.back();
  else window.close();
});

async function proceed(always: boolean): Promise<void> {
  if (!/^https?:\/\//i.test(target)) return;
  const ok: boolean = await chrome.runtime.sendMessage({ type: "AD_ALLOW", url: target, always } satisfies ExtMessage);
  if (ok) location.replace(target);
}
$("go").addEventListener("click", () => void proceed(false));
$("always").addEventListener("click", () => void proceed(true));
