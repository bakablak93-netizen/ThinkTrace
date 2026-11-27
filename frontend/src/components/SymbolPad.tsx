import type { RefObject } from "react";
import { t, type Lang } from "../i18n";

/** 10-key symbol pad for phones (CSS shows it only below 600 px). Inserts at the caret. */
const KEYS: { sym: string; insert: string | null; label: string }[] = [
  { sym: "x", insert: "x", label: "pad.x" },
  { sym: "+", insert: "+", label: "pad.plus" },
  { sym: "−", insert: "-", label: "pad.minus" },
  { sym: "×", insert: "*", label: "pad.times" },
  { sym: "÷", insert: "/", label: "pad.divide" },
  { sym: "=", insert: "=", label: "pad.equals" },
  { sym: "(", insert: "(", label: "pad.open" },
  { sym: ")", insert: ")", label: "pad.close" },
  { sym: ",", insert: ",", label: "pad.comma" },
  { sym: "⌫", insert: null, label: "pad.backspace" },
];

export function SymbolPad({ lang, inputRef, value, onChange }: {
  lang: Lang; inputRef: RefObject<HTMLInputElement>; value: string; onChange: (v: string) => void;
}) {
  function press(insert: string | null) {
    const el = inputRef.current;
    const start = el?.selectionStart ?? value.length;
    const end = el?.selectionEnd ?? value.length;
    let next: string, caret: number;
    if (insert === null) {
      const from = start === end ? Math.max(0, start - 1) : start;
      next = value.slice(0, from) + value.slice(end);
      caret = from;
    } else {
      next = value.slice(0, start) + insert + value.slice(end);
      caret = start + insert.length;
    }
    onChange(next);
    requestAnimationFrame(() => { el?.focus(); el?.setSelectionRange(caret, caret); });
  }
  return (
    <div className="symbols" role="group" aria-label={t(lang, "pad.title")}>
      {KEYS.map((k) => (
        <button key={k.label} type="button" onClick={() => press(k.insert)} aria-label={`${k.sym} ${t(lang, k.label)}`}>
          {k.sym}
        </button>
      ))}
    </div>
  );
}
