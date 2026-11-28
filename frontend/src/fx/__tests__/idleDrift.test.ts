import { afterEach, describe, expect, it, vi } from "vitest";
import { createEngine } from "../engine";
import { fakeGl } from "./fakeGl";

afterEach(() => vi.restoreAllMocks());

/** Mean particle speed (css px/s) with no cursor and no events, measured from the particle
 *  buffers the engine uploads, frame by frame (60 fps, after 3 s of settling). */
function measureIdleSpeed(seconds = 8): number {
  const frames: Float32Array[] = [];
  const canvas = document.createElement("canvas");
  vi.spyOn(canvas, "getContext").mockReturnValue(fakeGl((d) => frames.push(d)) as unknown as RenderingContext);
  let cb: FrameRequestCallback | null = null;
  const e = createEngine(canvas, { reducedMotion: false, raf: (f) => { cb = f; return 1; }, caf: () => {} })!;
  let now = performance.now();
  const total = Math.round((3 + seconds) * 60);
  for (let i = 0; i < total; i++) { now += 1000 / 60; const f = cb!; cb = null; f(now); }
  e.destroy();
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const used = frames.slice(frames.length - seconds * 60 - 1);
  const n = used[0].length / 7;
  let path = 0;
  for (let k = 1; k < used.length; k++)
    for (let i = 0; i < n; i++) {
      const dx = used[k][i * 7] - used[k - 1][i * 7], dy = used[k][i * 7 + 1] - used[k - 1][i * 7 + 1];
      const step = Math.hypot(dx, dy) / dpr;
      if (step < 50) path += step;   // ignore wrap-around jumps at the screen edges
    }
  return path / n / seconds;
}

describe("idle drift (no cursor): visible but calm", () => {
  it("mean particle speed stays within 12..18 px/s (prototype: ~4 px/s, hard to notice)", () => {
    const v = measureIdleSpeed();
    expect(v).toBeGreaterThanOrEqual(12);
    expect(v).toBeLessThanOrEqual(18);
  });
});
