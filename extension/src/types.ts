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
  | { type: "ANALYZE_EMAIL"; payload: EmailInfo }
  | { type: "ANALYZE_URL"; url: string; kind: "qr" | "manual" }
  | { type: "REPORT"; payload: ReportInfo }
  | { type: "AD_ALLOW"; url: string; always: boolean };
