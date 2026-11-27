import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createEngine, particleCount } from "../engine";
import { FxProvider, useFx } from "../FxProvider";
import { fakeGl } from "./fakeGl";

afterEach(() => vi.restoreAllMocks());

function Probe() {
  const fx = useFx();
  return <button onClick={() => { fx.pulse(1, 2, "ok"); fx.pulseFrom(null, "err"); fx.energy(1); }}>probe</button>;
}

describe("BackgroundFX without WebGL (jsdom)", () => {
  it("does not crash, hides the canvas and pulse() is a safe no-op", () => {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
    render(<FxProvider enabled><Probe /></FxProvider>);
    expect(screen.queryByTestId("fx-canvas")).toBeNull();     // canvas hidden -> CSS gradient
    expect(() => act(() => screen.getByText("probe").click())).not.toThrow();
  });

  it("survives a getContext that throws", () => {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(() => { throw new Error("no gl"); });
    expect(() => render(<FxProvider enabled><Probe /></FxProvider>)).not.toThrow();
    expect(screen.queryByTestId("fx-canvas")).toBeNull();
  });

  it("VITE_FX=off (enabled=false) renders no canvas at all", () => {
    const spy = vi.spyOn(HTMLCanvasElement.prototype, "getContext");
    render(<FxProvider enabled={false}><Probe /></FxProvider>);
    expect(screen.queryByTestId("fx-canvas")).toBeNull();
    expect(spy).not.toHaveBeenCalled();
  });
});

describe("animation loop", () => {
  function engine(reducedMotion: boolean) {
    const canvas = document.createElement("canvas");
    vi.spyOn(canvas, "getContext").mockReturnValue(fakeGl() as unknown as RenderingContext);
    const raf = vi.fn(() => 1);
    const caf = vi.fn();
    const e = createEngine(canvas, { reducedMotion, raf, caf });
    return { e, raf, caf };
  }

  it("prefers-reduced-motion: no animation loop, one static frame", () => {
    const { e, raf } = engine(true);
    expect(e).not.toBeNull();
    e!.pulse(10, 10, "solved");
    expect(raf).not.toHaveBeenCalled();
    e!.destroy();
  });

  it("normal motion: exactly one requestAnimationFrame is scheduled, cancelled on destroy", () => {
    const { e, raf, caf } = engine(false);
    expect(raf).toHaveBeenCalledTimes(1);
    e!.destroy();
    expect(caf).toHaveBeenCalledTimes(1);
  });
});

describe("particle count", () => {
  it("scales with area within 110..320, max 160 below 600 px", () => {
    expect(particleCount(320, 400)).toBe(110);
    expect(particleCount(1280, 900)).toBe(222);
    expect(particleCount(2560, 1440)).toBe(320);
    expect(particleCount(590, 2000)).toBe(160);
  });
});
