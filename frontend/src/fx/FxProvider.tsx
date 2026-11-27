import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { createEngine, type FxEngine, type PulseKind } from "./engine";

export type { PulseKind };

export interface FxApi {
  /** Visual pulse at viewport point (x, y). No-op when FX is off, unavailable or reduced motion. */
  pulse(x: number, y: number, kind: PulseKind): void;
  /** Pulse from the centre of an element (convenience). */
  pulseFrom(el: Element | null | undefined, kind: PulseKind): void;
  /** Short burst of particle energy (typing). */
  energy(amount: number): void;
}

const noop: FxApi = { pulse: () => {}, pulseFrom: () => {}, energy: () => {} };
const FxContext = createContext<FxApi>(noop);

export function useFx(): FxApi {
  return useContext(FxContext);
}

/** VITE_FX=off disables the layer (for the jury, slow machines and tests). */
export function fxEnabledByEnv(): boolean {
  return String(import.meta.env.VITE_FX ?? "").toLowerCase() !== "off";
}

function prefersReducedMotion(): boolean {
  return typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function FxProvider({ children, enabled = fxEnabledByEnv() }: { children: ReactNode; enabled?: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const engineRef = useRef<FxEngine | null>(null);
  const [available, setAvailable] = useState(enabled);
  const [reduced, setReduced] = useState(prefersReducedMotion);

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const on = () => setReduced(mq.matches);
    mq.addEventListener?.("change", on);
    return () => mq.removeEventListener?.("change", on);
  }, []);

  useEffect(() => {
    if (!enabled || !canvasRef.current) return;
    const engine = createEngine(canvasRef.current, { reducedMotion: reduced });
    engineRef.current = engine;
    setAvailable(engine !== null);     // no WebGL: hide the canvas, CSS gradient stays
    return () => { engine?.destroy(); engineRef.current = null; };
  }, [enabled, reduced]);

  const pulse = useCallback((x: number, y: number, kind: PulseKind) => engineRef.current?.pulse(x, y, kind), []);
  const api = useMemo<FxApi>(() => ({
    pulse,
    pulseFrom(el, kind) {
      if (!el) return;
      const r = el.getBoundingClientRect();
      pulse(r.left + r.width / 2, r.top + r.height / 2, kind);
    },
    energy: (a) => engineRef.current?.energy(a),
  }), [pulse]);

  // "tap": a small neutral wave from any button that is clicked
  useEffect(() => {
    if (!enabled) return;
    const onClick = (e: MouseEvent) => {
      const b = (e.target as Element | null)?.closest?.("button");
      if (b) api.pulseFrom(b, "tap");
    };
    document.addEventListener("click", onClick);
    return () => document.removeEventListener("click", onClick);
  }, [enabled, api]);

  return (
    <FxContext.Provider value={enabled && available ? api : noop}>
      {enabled && available && <canvas ref={canvasRef} className="fx-canvas" aria-hidden="true" data-testid="fx-canvas" />}
      {children}
    </FxContext.Provider>
  );
}
