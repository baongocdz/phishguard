export interface PageInfo {
  url: string;
  hostname: string;
  protocol: string;
  title: string;
  formCount: number;
  hasPasswordField: boolean;
  linkCount: number;
  externalLinkCount: number;
  textSnippet: string; // chữ hiển thị trên trang (đã cắt ngắn), cho Gemini đọc
  kind?: "page" | "qr" | "manual"; // trang đang mở hay link quét từ mã QR
  collectedAt: number;
}

export interface EmailInfo {
  sender: string; // "Tên <a@b.com>"
  replyTo: string;
  subject: string;
  body: string;
  links: { text: string; href: string }[];
}

export type Verdict = "safe" | "suspicious" | "phishing";

export interface AnalysisResult {
  verdict: Verdict;
  score: number; // 0..1
  reasons: string[];
  source: string;
  url?: string; // trang được chấm (extension tự gắn để popup so với tab hiện tại)
  breakdown?: { layer: string; label: string; points: number }[]; // mỗi lớp góp bao nhiêu điểm
}

/** Một dòng trong lịch sử cảnh báo (lưu ở chrome.storage.local, không gửi đi). */
export interface HistoryItem {
  url: string;
  verdict: Verdict;
  score: number;
  kind: "page" | "qr" | "email";
  at: number;
}

/** Cú bấm gần nhất trong một khung (clicktrack.ts), để nhận ra tab quảng cáo tự bật. */
export interface ClickInfo {
  at: number;
  href: string; // link được bấm ("" nếu bấm vào chỗ không phải link)
  overlay: boolean; // link trong suốt / phủ kín màn hình
}

/** Kết quả email đang mở trong Gmail, lưu theo tab để popup hiện lại. */
export interface EmailResult {
  url: string; // URL Gmail lúc phân tích (có #id thư)
  subject: string;
  sender: string;
  result: AnalysisResult;
}

export interface ReportInfo {
  url: string;
  hostname: string;
  kind: "false_positive" | "phishing";
  note: string;
}

export type ExtMessage =
  | { type: "PAGE_INFO"; payload: PageInfo }
  | { type: "SHOW_WARNING"; result: AnalysisResult }
  | { type: "GET_RESULT"; tabId: number }
  | { type: "ANALYZE_EMAIL"; payload: EmailInfo; pageUrl?: string }
  | { type: "ANALYZE_URL"; url: string; kind: "qr" | "manual" }
  | { type: "REPORT"; payload: ReportInfo }
  | { type: "AD_ALLOW"; url: string; always: boolean }
  | { type: "LAST_CLICK" }
  | { type: "GET_EMAIL_RESULT"; tabId: number };
