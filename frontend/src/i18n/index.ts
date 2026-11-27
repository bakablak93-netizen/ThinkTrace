import ru from "./ru";
import kk from "./kk";
import en from "./en";

export type Lang = "ru" | "kk" | "en";
export type Dict = Record<string, string>;

const dicts: Record<Lang, Dict> = { ru, kk, en };

// Missing key in kk/en falls back to ru, then to the key itself.
export function t(lang: Lang, key: string, params?: Record<string, string | number>): string {
  let s = dicts[lang][key] ?? dicts.ru[key] ?? key;
  if (params) for (const [k, v] of Object.entries(params)) s = s.replace(`{${k}}`, String(v));
  return s;
}
