import { t, type Lang } from "./i18n";

export type Confidence = "low" | "medium" | "high";
export type StepStatus = "correct" | "solved" | "error";

export interface StepView {
  event_id: number;
  text: string;
  latex: string;
  status: StepStatus;
}

export interface ProblemView {
  id: string;
  kind: "main" | "transfer";
  text: string;
  latex: string;
  current: string;
  solved: boolean;
  hints_enabled: boolean;
  steps: StepView[];
}

export interface Candidate {
  bug_id: string;
  name: string;
  confidence: number;
  level: "exact" | "solution";
}

export interface Diagnosis {
  unknown: boolean;
  ambiguous: boolean;
  pattern: "first" | "repeated" | null;
  candidates: Candidate[];
}

export type HintSource = "llm" | "template";

export interface HintView {
  level: number;
  text: string;
  source: HintSource;
}

export interface StepResult {
  status: StepStatus | "parse_error";
  event_id?: number;
  message?: string;
  diagnosis?: Diagnosis;
  hint?: HintView;
  problem?: ProblemView;
}

export interface ParseResult {
  ok: boolean;
  latex?: string;
  message?: string;
}

export interface ReportStep {
  event_id: number;
  t: number;
  text: string;
  status: StepStatus;
  self_confidence: Confidence;
  corrected: boolean;
  bugs: Candidate[];
  unknown: boolean;
  pattern: "first" | "repeated" | null;
  disagreed: boolean;
}

export interface ReportProblem {
  id: string;
  kind: "main" | "transfer";
  text: string;
  solved: boolean;
  duration_sec: number;
  steps: ReportStep[];
  hints: { t: number; level: number; kind: string; auto: boolean; source: HintSource }[];
  errors_by_bug: Record<string, number>;
}

export interface TimelineItem {
  t: number;
  type: string;
  problem_kind: "main" | "transfer" | null;
  text?: string;
  status?: string;
  level?: number;
  auto?: boolean;
  source?: HintSource;
}

export interface Report {
  note: string;
  summary: string;
  totals: { steps: number; errors: number; hints: number; corrections: number; disagreements: number };
  problems: ReportProblem[];
  transfer: { status: string; text: string };
  timeline: TimelineItem[];
}

export class ApiError extends Error {
  constructor(public code: string, public status: number) {
    super(code);
  }
}

export function errorMessage(lang: Lang, err: unknown): string {
  if (!(err instanceof ApiError)) return t(lang, "err.network");
  if (err.code === "rate_limited") return t(lang, "err.rate_limited");
  return t(lang, "err.generic", { code: err.code });
}

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(data.error ?? `http_${res.status}`, res.status);
  return data as T;
}

export const api = {
  start: (nickname: string, lang: Lang) =>
    call<{ session_id: string }>("POST", "/sessions", { nickname, lang }),
  newProblem: (sid: string, demo: boolean) =>
    call<ProblemView>("POST", `/sessions/${sid}/problems`, { demo }),
  transfer: (sid: string) => call<ProblemView>("POST", `/sessions/${sid}/transfer`),
  parse: (text: string, lang: Lang) => call<ParseResult>("POST", `/parse?lang=${lang}`, { text }),
  step: (sid: string, pid: string, text: string, confidence: Confidence, lang: Lang) =>
    call<StepResult>("POST", `/sessions/${sid}/problems/${pid}/steps?lang=${lang}`, { text, confidence }),
  hint: (sid: string, pid: string, lang: Lang) =>
    call<HintView>("POST", `/sessions/${sid}/problems/${pid}/hint?lang=${lang}`),
  disagree: (sid: string, eventId: number) =>
    call<{ ok: boolean }>("POST", `/sessions/${sid}/disagree`, { event_id: eventId }),
  finish: (sid: string) => call<{ ok: boolean }>("POST", `/sessions/${sid}/finish`),
  report: (sid: string, lang: Lang) => call<Report>("GET", `/sessions/${sid}/report?lang=${lang}`),
};
