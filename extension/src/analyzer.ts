import { API_BASE, API_TIMEOUT_MS } from "./config";
import type { AnalysisResult, PageInfo } from "./types";

const IPV4 = /^\d{1,3}(\.\d{1,3}){3}$/;

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