import type { ExtMessage } from "./types";

function readTarget(): string {
  const raw = location.hash.slice(1);
  try {
    return decodeURIComponent(raw);
  } catch {
    return raw; // URL có ký tự % lạ: dùng nguyên văn
  }
}
const target = readTarget();
const urlEl = document.getElementById("url")!;
urlEl.textContent = target || "(không rõ)";

// Đếm số lần chặn để hiện trong popup.
chrome.storage.local.get("adBlockedCount").then(({ adBlockedCount }) =>
  chrome.storage.local.set({ adBlockedCount: (Number(adBlockedCount) || 0) + 1 }));

document.getElementById("back")!.addEventListener("click", () => {
  // Tab mới do popunder mở ra thì không có trang trước: đóng luôn.
  if (history.length > 1) history.back();
  else window.close();
});

document.getElementById("go")!.addEventListener("click", async () => {
  if (!/^https?:\/\//i.test(target)) return;
  const ok: boolean = await chrome.runtime.sendMessage({ type: "AD_ALLOW", url: target } satisfies ExtMessage);
  if (ok) location.replace(target);
});
