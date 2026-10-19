// Chạy trong MỌI khung (cả iframe trình phát phim) từ lúc trang bắt đầu tải: báo cú bấm của người dùng
// cho background. Khi trang tự mở tab mới hoặc tự chuyển sang web khác ngay sau đó, background dùng thông
// tin này để phân biệt "người dùng bấm link thật" với "bấm nút Play / nền trang mà trang tự đẩy sang
// quảng cáo" (popunder, tab-under). Chỉ gửi loại cú bấm và link được bấm, không gửi nội dung trang.
import type { ClickInfo, ExtMessage } from "./types";

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
  if (!e.isTrusted || !chrome.runtime?.id) return; // cú bấm giả do script tạo ra / extension vừa tải lại
  const target = e.target as Element | null;
  const a = target?.closest?.("a[href]") as HTMLAnchorElement | null;
  const submit = target?.closest?.("button, input[type=submit], input[type=image]") as HTMLButtonElement | null;
  const click: ClickInfo = {
    at: Date.now(),
    href: a?.href ?? "",
    overlay: a ? isOverlay(a) : false,
    formSubmit: !!submit?.form && submit.type !== "button",
  };
  chrome.runtime.sendMessage({ type: "CLICK", click } satisfies ExtMessage).catch(() => {});
}

// Pha "capture" trên window: chạy trước mọi trình xử lý của trang.
window.addEventListener("pointerdown", record, true);
window.addEventListener("click", record, true);
