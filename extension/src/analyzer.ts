import { API_BASE, API_TIMEOUT_MS } from "./config";
import type { AnalysisResult, PageInfo } from "./types";

const IPV4 = /^\d{1,3}(\.\d{1,3}){3}$/;

// Giữ đồng bộ với BRANDS / SUSPICIOUS_TLDS / LURE_WORDS trong backend/app/heuristics.py.
const BRANDS: Record<string, string[]> = {
  paypal: ["paypal.com"],
  apple: ["apple.com", "icloud.com"],
  icloud: ["icloud.com", "apple.com"],
  microsoft: ["microsoft.com", "microsoftonline.com", "live.com", "office.com"],
  office365: ["office365.com", "office.com", "microsoft.com"],
  outlook: ["outlook.com", "live.com", "office.com", "office365.com"],
  google: ["google.com", "google.com.vn", "googleusercontent.com", "googleblog.com"],
  gmail: ["gmail.com", "google.com"],
  facebook: ["facebook.com", "fb.com"],
  instagram: ["instagram.com"],
  netflix: ["netflix.com"],
  amazon: ["amazon.com"],
  github: ["github.com", "github.io"],
  binance: ["binance.com"],
  zalo: ["zalo.me", "zaloapp.com"],
  shopee: ["shopee.vn"],
  lazada: ["lazada.vn"],
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

function isOfficial(host: string, domains: string[]): boolean {
  return domains.some((d) => host === d || host.endsWith("." + d));
}

/**
 * Bộ luật heuristic chạy cục bộ tại Extension, dùng khi backend lỗi hoặc offline.
 */
export async function analyzeLocal(info: PageInfo): Promise<AnalysisResult> {
  const reasons: string[] = [];
  let score = 0;

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
    if (brand) {
      score += 0.4;
      reasons.push(`Tên miền chứa tên thương hiệu '${brand}' nhưng không phải tên miền chính thức.`);
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