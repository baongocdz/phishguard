import jsQR from "jsqr";
import { API_BASE } from "./config";
import type { AnalysisResult, ExtMessage } from "./types";

const LABEL = { safe: "An toàn", suspicious: "Đáng ngờ", phishing: "Lừa đảo" } as const;
const SOURCE: Record<string, string> = {
  blacklist: "danh sách đen", whitelist: "danh sách tin cậy", cache: "kết quả đã lưu",
  heuristic: "bộ luật + học máy", gemini: "bộ luật + AI Gemini", email: "bộ luật email",
  local: "bộ luật trên máy (không kết nối được máy chủ)",
};
const $ = (id: string) => document.getElementById(id)!;

function renderReasons(list: HTMLElement, reasons: string[]): void {
  list.replaceChildren(
    ...reasons.map((reason) => {
      const li = document.createElement("li");
      li.textContent = reason;
      return li;
    }),
  );
}

// ---------- Kết quả của tab hiện tại + nút báo sai ----------
async function showTabResult(tab: chrome.tabs.Tab | undefined): Promise<void> {
  const verdictEl = $("verdict");
  $("url").textContent = tab?.url ?? "";

  const result: AnalysisResult | null = tab?.id
    ? await chrome.runtime.sendMessage({ type: "GET_RESULT", tabId: tab.id } satisfies ExtMessage)
    : null;

  if (!result) {
    verdictEl.className = "chip none";
    verdictEl.textContent = "Chưa có dữ liệu (thử tải lại trang)";
    return;
  }

  verdictEl.className = `chip ${result.verdict}`;
  verdictEl.textContent = `${LABEL[result.verdict]} · điểm ${result.score}`;
  renderReasons($("reasons"), result.reasons);
  $("source").textContent = `Nguồn kết quả: ${SOURCE[result.source] ?? result.source}`;

  let url: URL;
  try {
    url = new URL(tab!.url!);
  } catch {
    return;
  }
  if (!/^https?:$/.test(url.protocol)) return;
  const kind = result.verdict === "safe" ? "phishing" : "false_positive";
  const btn = $("report") as HTMLButtonElement;
  btn.textContent = kind === "phishing" ? "🚩 Báo trang này là lừa đảo" : "✅ Báo chặn nhầm (trang an toàn)";
  btn.classList.remove("hidden");
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    const ok: boolean = await chrome.runtime.sendMessage({
      type: "REPORT",
      payload: { url: url.href, hostname: url.hostname, kind, note: "extension" },
    } satisfies ExtMessage);
    $("report-msg").textContent = ok ? "Đã gửi, cảm ơn bạn!" : "Gửi thất bại, thử lại sau.";
  });
}

// ---------- Quét mã QR đang hiện trên màn hình (quishing) ----------
function findQr(img: ImageBitmap): string | null {
  const canvas = new OffscreenCanvas(img.width, img.height);
  const ctx = canvas.getContext("2d", { willReadFrequently: true })!;
  ctx.drawImage(img, 0, 0);
  // Thử cả màn hình trước, rồi từng góc phần tư (giúp khi có nhiều mã/ảnh nhỏ).
  const w = img.width, h = img.height;
  const regions: [number, number, number, number][] = [
    [0, 0, w, h], [0, 0, w / 2, h / 2], [w / 2, 0, w / 2, h / 2],
    [0, h / 2, w / 2, h / 2], [w / 2, h / 2, w / 2, h / 2], [w / 4, h / 4, w / 2, h / 2],
  ];
  for (const [x, y, rw, rh] of regions) {
    const data = ctx.getImageData(Math.round(x), Math.round(y), Math.round(rw), Math.round(rh));
    const code = jsQR(data.data, data.width, data.height, { inversionAttempts: "attemptBoth" });
    if (code?.data) return code.data;
  }
  return null;
}

async function scanQr(): Promise<void> {
  const btn = $("scan-qr") as HTMLButtonElement;
  const out = $("qr-result");
  btn.disabled = true;
  out.textContent = "Đang chụp và đọc màn hình…";
  try {
    const dataUrl = await chrome.tabs.captureVisibleTab({ format: "png" });
    const img = await createImageBitmap(await (await fetch(dataUrl)).blob());
    const text = findQr(img);
    if (!text) {
      out.textContent = "Không thấy mã QR nào trên màn hình. Cuộn để mã QR hiện rõ rồi thử lại.";
      return;
    }
    const box = document.createElement("div");
    box.className = "qr-box";
    const content = document.createElement("div");
    content.className = "url";
    content.textContent = `Nội dung mã QR: ${text}`;
    box.append(content);
    out.replaceChildren(box);

    if (!/^https?:\/\//i.test(text)) {
      const note = document.createElement("div");
      note.textContent = "Mã QR không chứa link web. Cẩn thận nếu nó yêu cầu chuyển tiền hoặc kết nối Wi-Fi lạ.";
      box.append(note);
      return;
    }
    const r: AnalysisResult | null = await chrome.runtime.sendMessage(
      { type: "ANALYZE_URL", url: text, kind: "qr" } satisfies ExtMessage,
    );
    if (!r) {
      box.append("Không phân tích được link này.");
      return;
    }
    box.className = `qr-box ${r.verdict}`;
    const chip = document.createElement("span");
    chip.className = `chip ${r.verdict}`;
    chip.textContent = `${LABEL[r.verdict]} · điểm ${r.score}`;
    const list = document.createElement("ul");
    renderReasons(list, r.reasons);
    box.append(chip, list);
  } catch (e) {
    out.textContent = "Không chụp được màn hình của tab này (trang hệ thống của Chrome không cho phép).";
  } finally {
    btn.disabled = false;
  }
}

// ---------- Bật/tắt phân tích Gmail ----------
async function setupGmailToggle(): Promise<void> {
  const box = $("gmail-scan") as HTMLInputElement;
  const { gmailScan } = await chrome.storage.local.get("gmailScan");
  box.checked = gmailScan !== false;
  box.addEventListener("change", () => void chrome.storage.local.set({ gmailScan: box.checked }));
}

// ---------- Bật/tắt chặn chuyển hướng quảng cáo ----------
async function setupAdToggle(): Promise<void> {
  const box = $("ad-block") as HTMLInputElement;
  const { adBlock, adBlockedCount } = await chrome.storage.local.get(["adBlock", "adBlockedCount"]);
  box.checked = adBlock !== false;
  $("ad-count").textContent = `Đã chặn ${Number(adBlockedCount) || 0} lần chuyển hướng quảng cáo.`;
  box.addEventListener("change", () => void chrome.storage.local.set({ adBlock: box.checked }));
}

async function main(): Promise<void> {
  ($("open-web") as HTMLAnchorElement).href = `${API_BASE}/`;
  ($("open-dash") as HTMLAnchorElement).href = `${API_BASE}/dashboard`;
  $("scan-qr").addEventListener("click", () => void scanQr());
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  await Promise.all([showTabResult(tab), setupGmailToggle(), setupAdToggle()]);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => void main());
} else {
  void main();
}
