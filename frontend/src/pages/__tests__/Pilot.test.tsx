import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ProblemView } from "../../api";
import { readPilotCode } from "../../pilot";

const pulses: string[] = [];
vi.mock("../../fx/engine", () => ({
  createEngine: () => ({ pulse: (_x: number, _y: number, k: string) => pulses.push(k), energy: () => {}, destroy: () => {} }),
  particleCount: () => 110,
}));
const startPilot = vi.fn();
const step = vi.fn();
vi.mock("../../api", async (orig) => {
  const real = await orig<typeof import("../../api")>();
  return { ...real, api: { ...real.api, startPilot: (...a: unknown[]) => startPilot(...a), step: (...a: unknown[]) => step(...a) } };
});

import { FxProvider } from "../../fx/FxProvider";
import { Consent } from "../Consent";
import { ExamProblem } from "../ExamProblem";

describe("pilot code from the link", () => {
  it.each([["?pilot=class7b", "class7b"], ["?pilot=A_1-b", "A_1-b"], ["?pilot=" + "x".repeat(24), "x".repeat(24)]])(
    "%s is accepted", (q, code) => expect(readPilotCode(q)).toBe(code));
  it.each(["", "?pilot=", "?pilot=" + "x".repeat(25), "?pilot=bad%20code", "?pilot=a/b", "?pilot=%D0%BA%D0%BB%D0%B0%D1%81%D1%81", "?other=1"])(
    "%s is ignored", (q) => expect(readPilotCode(q)).toBeNull());
});

describe("consent screen", () => {
  beforeEach(() => startPilot.mockReset());

  it("start is blocked until the checkbox is ticked", async () => {
    startPilot.mockResolvedValue({ session_id: "s", token: "t", pilot: { cohort: "c", phase: "pre" } });
    const onStarted = vi.fn();
    render(<Consent lang="ru" cohort="class7b" onStarted={onStarted} />);
    const btn = screen.getByRole("button", { name: "Начать" }) as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
    await act(async () => { fireEvent.submit(btn.closest("form")!); });
    expect(startPilot).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("checkbox"));
    expect(btn.disabled).toBe(false);
    await act(async () => { fireEvent.click(btn); });
    expect(startPilot).toHaveBeenCalledWith("class7b", "ru");
    expect(onStarted).toHaveBeenCalled();
    expect(screen.getByText(/нужно согласие родителей или опекуна/)).toBeTruthy();
  });
});

describe("exam problem", () => {
  beforeEach(() => { pulses.length = 0; step.mockReset(); });
  const prob = (steps: ProblemView["steps"]): ProblemView => ({
    id: "p", kind: "exam", text: "-2x + 7 = 1", latex: "", current: "", solved: false, hints_enabled: false,
    steps, bank_id: "A3", level: "A", phase: "pre", finished: false });

  it("shows no verdict and makes no ok/err/solved effects", async () => {
    step.mockResolvedValue({ status: "recorded", event_id: 1, finished: false,
      problem: prob([{ event_id: 1, text: "-2x = 8", latex: "-2x = 8", status: "recorded" }]) });
    const onProblem = vi.fn();
    render(<FxProvider enabled><ExamProblem lang="ru" sid="s" problem={prob([])} index={1} total={3}
      onProblem={onProblem} onDone={() => {}} /></FxProvider>);
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({} as RenderingContext);
    fireEvent.change(screen.getByLabelText(/Напиши/), { target: { value: "-2x = 8" } });
    fireEvent.click(screen.getByRole("button", { name: "Уверен" }));
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Записать шаг" })); });
    expect(screen.getByText("Шаг записан.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Подсказка/ })).toBeNull();
    expect(pulses.filter((k) => ["ok", "err", "solved", "ai"].includes(k))).toEqual([]);
    expect(screen.queryByText(/Верно|Ошибка/)).toBeNull();
  });
});
