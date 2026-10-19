// Chạy trong MỌI khung (cả iframe trình phát phim) từ lúc trang bắt đầu tải: ghi lại cú bấm
// gần nhất của người dùng. Khi trang tự mở tab mới, background hỏi lại để phân biệt
// "người dùng bấm link thật" với "bấm nút Play / nền trang mà trang tự bật tab quảng cáo"
// (popunder). Không gửi gì đi đâu, chỉ trả lời khi background hỏi.
import type { ClickInfo, ExtMessage } from "./types";

let last: ClickInfo | null = null;

// Link trong suốt hoặc phủ gần kín màn hình: mẹo của web lậu để cú bấm nào cũng trúng quảng cáo.
function isOverlay(a: HTMLAnchorElement): boolean {
  const r = a.getBoundingClientRect();
  if (r.width * r.height >= 0.4 * innerWidth * innerHeight) return true;
  for (let el: Element | null = a; el; el = el.parentElement) {
    if (Number(getComputedStyle(el).opacity) < 0.1) return true;
  }
  return false;
}

function record(e: Event): void {
  if (!e.isTrusted) return; // cú bấm giả do script của trang tạo ra thì không tính
  const a = (e.target as Element | null)?.closest?.("a[href]") as HTMLAnchorElement | null;
  last = { at: Date.now(), href: a?.href ?? "", overlay: a ? isOverlay(a) : false };
}

// Pha "capture" trên window: chạy trước mọi trình xử lý của trang.
window.addEventListener("pointerdown", record, true);
window.addEventListener("click", record, true);

chrome.runtime.onMessage.addListener((msg: ExtMessage, _sender, sendResponse) => {
  if (msg.type === "LAST_CLICK") sendResponse(last);
  return false;
});
