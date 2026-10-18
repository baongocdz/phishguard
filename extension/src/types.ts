export interface PageInfo {
  url: string;
  hostname: string;
  protocol: string;
  title: string;
  formCount: number;
  hasPasswordField: boolean;
  linkCount: number;
  externalLinkCount: number;
  collectedAt: number;
}

export type Verdict = "safe" | "suspicious" | "phishing";

export interface AnalysisResult {
  verdict: Verdict;
  score: number; // 0..1
  reasons: string[];
  source: string;
}

export type ExtMessage =
  | { type: "PAGE_INFO"; payload: PageInfo }
  | { type: "SHOW_WARNING"; result: AnalysisResult }
  | { type: "GET_RESULT"; tabId: number };
