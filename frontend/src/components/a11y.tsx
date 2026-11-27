import { useEffect, useRef, useState } from "react";
import { t, type Lang } from "../i18n";

/** Step status shown by icon + text, not only by colour. */
export function StatusChip({ lang, status }: { lang: Lang; status: string }) {
  const icon = status === "error" ? "✗" : "✓";
  return (
    <span className={`chip ${status}`}>
      <span aria-hidden="true">{icon} </span>{t(lang, `status.${status}`)}
    </span>
  );
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
    <div className="font-size" role="group" aria-label={t(lang, "a11y.font_size")}>
      <button type="button" onClick={() => setScale(SCALES[i - 1])} disabled={i === 0}>
        A−<span className="sr-only"> {t(lang, "a11y.font_smaller")}</span>
      </button>
      <span className="small" aria-live="polite">{Math.round(scale * 100)}%</span>
      <button type="button" onClick={() => setScale(SCALES[i + 1])} disabled={i === SCALES.length - 1}>
        A+<span className="sr-only"> {t(lang, "a11y.font_larger")}</span>
      </button>
    </div>
  );
}
