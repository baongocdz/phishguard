import type { ExtMessage } from "./types";

// Hash có dạng "<loại>|<url>": ad, aff, mk (adblock.ts) hoặc pop (popunder.ts).
type Kind = "ad" | "aff" | "pop" | "mk";
function readHash(): { kind: Kind; url: string } {
  let raw = location.hash.slice(1);
  try {
    raw = decodeURIComponent(raw);
  } catch {
    // URL có ký tự % lạ: dùng nguyên văn
  }
  const sep = raw.indexOf("|");
  const prefix = sep > 0 ? raw.slice(0, sep) : "";
  if (["ad", "aff", "pop", "mk"].includes(prefix)) return { kind: prefix as Kind, url: raw.slice(sep + 1) };
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
} else if (kind === "pop") {
  document.title = "PhishGuard đã chặn tab quảng cáo tự bật";
  $("title").textContent = "🛡️ Đã chặn tab quảng cáo tự bật";
  $("lead").textContent = "Trang bạn vừa xem tự mở tab mới sang một trang web khác khi bạn bấm vào chỗ không phải là link (kiểu quảng cáo popunder của web phim/truyện lậu):";
  $("tip1").textContent = "Những tab này thường dẫn tới cờ bạc trực tuyến, trúng thưởng giả, ứng dụng lạ hoặc trang lừa đảo.";
  $("tip2").textContent = "Nếu đúng là bạn muốn mở trang này (vd nút thanh toán, đăng nhập), bấm “Mở lần này”.";
} else if (kind === "mk") {
  document.title = "PhishGuard: đây là trang đích của quảng cáo bật lên";
  $("title").textContent = "🛡️ Đây là trang đích của quảng cáo bật lên";
  $("lead").textContent = "Địa chỉ trang tự ghi là đến từ quảng cáo dạng bật lên (popup / popunder):";
  $("tip1").textContent = "Loại quảng cáo này trên web phim/truyện lậu gần như luôn dẫn tới cờ bạc, cá độ, trúng thưởng giả hoặc ứng dụng lạ.";
  $("tip2").textContent = "Nếu bạn vẫn muốn xem, bấm “Mở lần này”. PhishGuard sẽ tiếp tục cảnh báo nếu trang có dấu hiệu nguy hiểm.";
}

// Đếm số lần chặn để hiện trong popup.
chrome.storage.local.get("adBlockedCount").then(({ adBlockedCount }) =>
  chrome.storage.local.set({ adBlockedCount: (Number(adBlockedCount) || 0) + 1 }));

$("back").addEventListener("click", () => {
  // Tab mới do popunder mở ra thì không có trang trước (hoặc trang trước chính là quảng cáo): đóng luôn.
  if (kind !== "pop" && history.length > 1) history.back();
  else void chrome.tabs.getCurrent().then((t) => (t?.id !== undefined ? chrome.tabs.remove(t.id) : window.close()));
});

async function proceed(always: boolean): Promise<void> {
  if (!/^https?:\/\//i.test(target)) return;
  const ok: boolean = await chrome.runtime.sendMessage({ type: "AD_ALLOW", url: target, always } satisfies ExtMessage);
  if (ok) location.replace(target);
}
$("go").addEventListener("click", () => void proceed(false));
$("always").addEventListener("click", () => void proceed(true));
