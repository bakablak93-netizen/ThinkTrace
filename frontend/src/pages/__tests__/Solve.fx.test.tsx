import { act, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ProblemView, StepResult } from "../../api";

// fake FX engine: records pulse kinds
const pulses: string[] = [];
vi.mock("../../fx/engine", () => ({
  createEngine: () => ({ pulse: (_x: number, _y: number, k: string) => pulses.push(k), energy: () => {}, destroy: () => {} }),
  particleCount: () => 110,
}));

const step = vi.fn<(...a: unknown[]) => Promise<StepResult>>();
const hint = vi.fn();
vi.mock("../../api", async (orig) => {
  const real = await orig<typeof import("../../api")>();
  return { ...real, api: { ...real.api, step: (...a: unknown[]) => step(...a), hint: (...a: unknown[]) => hint(...a),
    parse: () => Promise.resolve({ ok: false }) } };
});

import { FxProvider } from "../../fx/FxProvider";
import { Solve } from "../Solve";

function problem(steps: ProblemView["steps"], solved = false): ProblemView {
  return { id: "p1", kind: "main", text: "2(x + 3) = 14", latex: "2(x+3)=14", current: "", solved,
    hints_enabled: true, steps };
}
const s = (id: number, text: string, status: "correct" | "error" | "solved") => ({ event_id: id, text, latex: text, status });

function Harness() {
  const [p, setP] = useState(problem([]));
  return <Solve lang="ru" sid="s1" problem={p} onProblem={setP} onTransfer={() => {}} onReport={() => {}} />;
}

async function submit(text: string) {
  fireEvent.change(screen.getByLabelText(/Напиши/), { target: { value: text } });
  fireEvent.click(screen.getByRole("button", { name: "Уверен" }));
  await act(async () => { fireEvent.submit(screen.getByRole("button", { name: "Проверить" }).closest("form")!); });
  await act(async () => { await new Promise((r) => setTimeout(r, 30)); });
}

describe("Solve -> FX pulses", () => {
  beforeEach(() => {
    pulses.length = 0;
    step.mockReset();
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({} as RenderingContext);
  });

  it("err + ai on a wrong step with a hint, ok on a correct step, solved at the end", async () => {
    render(<FxProvider enabled><Harness /></FxProvider>);

    step.mockResolvedValueOnce({ status: "error", event_id: 1,
      diagnosis: { unknown: false, ambiguous: false, pattern: "first", candidates: [] },
      hint: { level: 1, text: "Проверь скобки", source: "llm" },
      problem: problem([s(1, "2x + 3 = 14", "error")]) });
    await submit("2x+3=14");
    expect(pulses).toContain("err");
    expect(pulses).toContain("ai");
    expect(screen.getByText(/Подсказка ИИ · 1 из 4/)).toBeTruthy();

    pulses.length = 0;
    step.mockResolvedValueOnce({ status: "correct", event_id: 2,
      problem: problem([s(1, "2x + 3 = 14", "error"), s(2, "2x + 6 = 14", "correct")]) });
    await submit("2x+6=14");
    expect(pulses.filter((k) => k !== "tap" && k !== "key")).toEqual(["ok"]);

    pulses.length = 0;
    step.mockResolvedValueOnce({ status: "solved", event_id: 3,
      problem: problem([s(1, "2x + 3 = 14", "error"), s(2, "2x + 6 = 14", "correct"), s(3, "x = 4", "solved")], true) });
    await submit("x=4");
    expect(pulses.filter((k) => k !== "tap" && k !== "key")).toEqual(["solved"]);
    expect(screen.getByText("Решено", { selector: "h2" })).toBeTruthy();
  });

  it("template hint is labelled without 'ИИ'", async () => {
    render(<FxProvider enabled><Harness /></FxProvider>);
    step.mockResolvedValueOnce({ status: "error", event_id: 1,
      diagnosis: { unknown: true, ambiguous: false, pattern: "first", candidates: [] },
      hint: { level: 1, text: "Проверь шаг", source: "template" },
      problem: problem([s(1, "2x = 7", "error")]) });
    await submit("2x=7");
    expect(screen.getByText(/^Подсказка · 1 из 4$/)).toBeTruthy();
    expect(screen.queryByText(/Подсказка ИИ/)).toBeNull();
  });
});
