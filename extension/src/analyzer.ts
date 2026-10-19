import { API_BASE, API_TIMEOUT_MS, EMAIL_TIMEOUT_MS } from "./config";
import type { AnalysisResult, EmailInfo, PageInfo, ReportInfo } from "./types";

const IPV4 = /^\d{1,3}(\.\d{1,3}){3}$/;

/** Thiết bị trong mạng nội bộ (modem 192.168.1.1, NAS...). Giữ giống is_lan_host ở backend:
 *  127.0.0.1 không tính để trang demo chạy ở máy vẫn được chấm. */
export function isLanHost(hostname: string): boolean {
  const host = hostname.toLowerCase().replace(/\.$/, "");
  if ([".local", ".lan", ".home", ".home.arpa", ".internal"].some((s) => host.endsWith(s))) return true;
  if (!IPV4.test(host)) return false;
  const [a, b] = host.split(".").map(Number);
  return a === 10 || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168) || (a === 169 && b === 254);
}

// Giữ đồng bộ với BRANDS / SUSPICIOUS_TLDS / LURE_WORDS trong backend/app/heuristics.py.
const BRANDS: Record<string, string[]> = {
  paypal: ["paypal.com"],
  apple: ["apple.com", "icloud.com"],
  icloud: ["icloud.com", "apple.com"],
  microsoft: ["microsoft.com", "microsoftonline.com", "live.com", "office.com"],
  office365: ["office365.com", "office.com", "microsoft.com"],
  outlook: ["outlook.com", "live.com", "office.com", "office365.com"],
  google: ["google.com", "google.com.vn", "googleusercontent.com", "googleblog.com", "c.gle", "g.co", "goo.gle"],
  gmail: ["gmail.com", "google.com"],
  facebook: ["facebook.com", "fb.com", "facebook.net", "fbcdn.net"],
  instagram: ["instagram.com"],
  netflix: ["netflix.com"],
  amazon: ["amazon.com", "amazonaws.com", "amazon.co.jp", "amazon.de"],
  github: ["github.com", "github.io"],
  binance: ["binance.com"],
  zalo: ["zalo.me", "zaloapp.com"],
  shopee: ["shopee.vn"],
  lazada: ["lazada.vn", "lazada.co.th", "lazada.com.my", "lazada.sg", "lazada.co.id", "lazada.com.ph"],
  vietcombank: ["vietcombank.com.vn"],
  techcombank: ["techcombank.com", "techcombank.com.vn"],
  vietinbank: ["vietinbank.vn"],
  agribank: ["agribank.com.vn"],
  bidv: ["bidv.com.vn"],
  mbbank: ["mbbank.com.vn"],
  tpbank: ["tpb.vn", "tpbank.vn"],
  sacombank: ["sacombank.com.vn"],
  momo: ["momo.vn"],
};

const SUSPICIOUS_TLDS = new Set([
  "top", "xyz", "click", "icu", "buzz", "cyou", "rest", "monster", "sbs", "cfd",
  "quest", "tk", "ml", "ga", "cf", "gq", "zip", "mov",
]);

const LURE_WORDS = [
  "login", "signin", "verify", "secure", "security", "account", "update",
  "confirm", "recover", "unlock", "xacminh", "xacthuc", "dangnhap", "baomat",
  "khoataikhoan",
];

const LEET: Record<string, string> = { "0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t" };

/** Tách tên miền theo '.' và '-', đổi chữ số giả chữ cái về chữ (faceb00k -> facebook). */
function tokens(host: string): string[] {
  return host
    .split(/[.-]/)
    .filter(Boolean)
    .map((t) => t.replace(/[013457]/g, (c) => LEET[c]));
}

/** Tên miền chính thức của một thương hiệu trong BRANDS (accounts.google.com, momo.vn...). */
export function isOfficialBrandHost(host: string): boolean {
  return Object.values(BRANDS).some((domains) => isOfficial(host, domains));
}

function isOfficial(host: string, domains: string[]): boolean {
  return domains.some((d) => host === d || host.endsWith("." + d));
}

// Giữ đồng bộ với lookalike_brand trong backend/app/heuristics.py.
const HOMOGLYPHS: [string, string][] = [["rn", "m"], ["vv", "w"]];

function editDistance(a: string, b: string, limit: number): number {
  if (Math.abs(a.length - b.length) > limit) return limit + 1;
  let prev = Array.from({ length: b.length + 1 }, (_, j) => j);
  for (let i = 1; i <= a.length; i++) {
    const cur = [i];
    for (let j = 1; j <= b.length; j++) {
      cur.push(Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1)));
    }
    if (Math.min(...cur) > limit) return limit + 1;
    prev = cur;
  }
  return prev[b.length];
}

/** Thương hiệu mà tên miền "na ná" (vietcornbank, netfllx...). */
function lookalikeBrand(host: string, parts: string[]): string | undefined {
  for (const [b, official] of Object.entries(BRANDS)) {
    if (b.length < 6 || isOfficial(host, official)) continue;
    const limit = b.length >= 9 ? 2 : 1;
    for (const t of parts) {
      const fixed = HOMOGLYPHS.reduce((s, [fake, real]) => s.split(fake).join(real), t);
      if (fixed !== t && fixed.startsWith(b)) return b;
      if (t !== b && editDistance(t, b, limit) <= limit) return b;
    }
  }
  return undefined;
}

/**
 * Bộ luật heuristic chạy cục bộ tại Extension, dùng khi backend lỗi hoặc offline.
 */
export async function analyzeLocal(info: Pick<PageInfo, "url" | "hostname" | "protocol" | "hasPasswordField">): Promise<AnalysisResult> {
  const reasons: string[] = [];
  let score = 0;
  if (isLanHost(info.hostname)) {
    return { verdict: "safe", score: 0, reasons: ["Thiết bị trong mạng nội bộ — không xét lừa đảo."], source: "local" };
  }

  if (info.protocol !== "https:") {
    score += 0.2;
    reasons.push("Trang không dùng HTTPS.");
  }
  if (IPV4.test(info.hostname)) {
    score += 0.4;
    reasons.push("Địa chỉ trang là IP thay vì tên miền.");
  }
  if (info.url.includes("@")) {
    score += 0.3;
    reasons.push("URL chứa ký tự '@' (có thể che giấu tên miền thật).");
  }
  if (info.hostname.length > 40 || (info.hostname.match(/-/g) ?? []).length >= 3) {
    score += 0.2;
    reasons.push("Tên miền quá dài hoặc có nhiều dấu gạch ngang.");
  }
  if (info.hostname.includes("xn--")) {
    score += 0.3;
    reasons.push("Tên miền dùng punycode (có thể giả mạo ký tự).");
  }
  if (info.hasPasswordField && info.protocol !== "https:") {
    score += 0.4;
    reasons.push("Có ô nhập mật khẩu trên kết nối không an toàn.");
  }

  const host = info.hostname.toLowerCase().replace(/\.$/, "");
  if (!IPV4.test(host)) {
    const parts = tokens(host);
    // Chỉ khớp khi thương hiệu đứng đầu một cụm: "pineapple" không bị coi là "apple".
    const brand = Object.keys(BRANDS).find(
      (b) => parts.some((t) => t.startsWith(b)) && !isOfficial(host, BRANDS[b]),
    );
    const lookalike = brand ? undefined : lookalikeBrand(host, parts);
    if (brand) {
      score += 0.4;
      reasons.push(`Tên miền chứa tên thương hiệu '${brand}' nhưng không phải tên miền chính thức.`);
    } else if (lookalike) {
      score += 0.4;
      reasons.push(`Tên miền na ná thương hiệu '${lookalike}' (dùng ký tự gần giống để đánh lừa).`);
    }
    if (SUSPICIOUS_TLDS.has(host.split(".").pop() ?? "")) {
      score += 0.2;
      reasons.push("Đuôi tên miền thường bị dùng cho trang lừa đảo.");
    }
    if (parts.some((t) => LURE_WORDS.some((w) => t.includes(w)))) {
      score += 0.2;
      reasons.push("Tên miền chứa từ ngữ dụ đăng nhập/xác minh.");
    }
  }

  score = Math.min(1, Number(score.toFixed(2)));
  const verdict = score >= 0.6 ? "phishing" : score >= 0.3 ? "suspicious" : "safe";
  return { verdict, score, reasons, source: "local" };
}

/**
 * Hàm phân tích chính: Gọi Backend FastAPI để kiểm tra Whitelist/Blacklist/Cache/Heuristic.
 * Nếu Backend lỗi hoặc quá API_TIMEOUT_MS, tự động lùi về analyzeLocal.
 */
export async function analyze(info: PageInfo): Promise<AnalysisResult> {
  // Địa chỉ mạng nội bộ: chấm tại chỗ, không gửi lên máy chủ.
  if (isLanHost(info.hostname)) return analyzeLocal(info);
  try {
    const res = await fetch(`${API_BASE}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(info),
      signal: AbortSignal.timeout(API_TIMEOUT_MS),
    });

    if (!res.ok) {
      throw new Error(String(res.status));
    }

    return (await res.json()) as AnalysisResult;
  } catch {
    return analyzeLocal(info);
  }
}
async function postJson<T>(path: string, body: unknown, timeoutMs = API_TIMEOUT_MS): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!res.ok) throw new Error(String(res.status));
  return (await res.json()) as T;
}

/** Phân tích email/tin nhắn. Không có bộ luật email cục bộ nên lỗi thì trả null. */
export async function analyzeEmail(email: EmailInfo): Promise<AnalysisResult | null> {
  try {
    return await postJson<AnalysisResult>("/analyze-email", email, EMAIL_TIMEOUT_MS);
  } catch {
    return null;
  }
}

/** Phân tích một URL rời (vd lấy từ mã QR), không có thông tin trang. */
export async function analyzeUrl(raw: string, kind: "qr" | "manual"): Promise<AnalysisResult | null> {
  let u: URL;
  try {
    u = new URL(raw);
  } catch {
    return null;
  }
  return analyze({
    url: u.href, hostname: u.hostname, protocol: u.protocol, title: "",
    formCount: 0, hasPasswordField: false, linkCount: 0, externalLinkCount: 0,
    textSnippet: "", kind, collectedAt: Date.now(),
  });
}

export async function sendReport(report: ReportInfo): Promise<boolean> {
  try {
    await postJson("/report", report);
    return true;
  } catch {
    return false;
  }
}
