import { useEffect, useRef, useState } from "react";
import { t, type Lang } from "../i18n";

const BADGE: Record<string, string> = { correct: "ok", solved: "solved", error: "err" };

/** Step status as a text badge (never colour only). */
export function StatusChip({ lang, status }: { lang: Lang; status: string }) {
  return <span className={`badge ${BADGE[status] ?? "ok"}`}>{t(lang, `status.${status}`)}</span>;
}

/** Heading that receives focus when a screen opens (keyboard and screen-reader users land on it). */
export function useFocusOnMount<T extends HTMLElement>(dep?: unknown) {
  const ref = useRef<T>(null);
  useEffect(() => { ref.current?.focus(); }, [dep]);
  return ref;
}

const SCALES = [0.875, 1, 1.125, 1.25, 1.5];
const KEY = "tt-font-scale";

function readScale(): number {
  try {
    const v = Number(localStorage.getItem(KEY));
    return SCALES.includes(v) ? v : 1;
  } catch {
    return 1;
  }
}

/** A− / A+ buttons: scale the root font size (all sizes are in rem). Remembered per browser. */
export function FontSizeControl({ lang }: { lang: Lang }) {
  const [scale, setScale] = useState(readScale);
  useEffect(() => {
    document.documentElement.style.fontSize = `${scale * 100}%`;
    try { localStorage.setItem(KEY, String(scale)); } catch { /* storage may be unavailable */ }
  }, [scale]);
  const i = SCALES.indexOf(scale);
  return (
    <div className="tools" role="group" aria-label={t(lang, "a11y.font_size")}>
      <button type="button" className="icon" onClick={() => setScale(SCALES[i - 1])} disabled={i === 0}>
        A−<span className="sr-only"> {t(lang, "a11y.font_smaller")}</span>
      </button>
      <span className="small muted" aria-live="polite">{Math.round(scale * 100)}%</span>
      <button type="button" className="icon" onClick={() => setScale(SCALES[i + 1])} disabled={i === SCALES.length - 1}>
        A+<span className="sr-only"> {t(lang, "a11y.font_larger")}</span>
      </button>
    </div>
  );
}
