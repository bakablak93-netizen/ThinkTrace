import ru from "./ru";
import kk from "./kk";
import en from "./en";

export type Lang = "ru" | "kk" | "en";
export type Dict = Record<string, string>;

const dicts: Record<Lang, Dict> = { ru, kk, en };

// Missing key in kk/en falls back to ru, then to the key itself.
export function t(lang: Lang, key: string): string {
  return dicts[lang][key] ?? dicts.ru[key] ?? key;
}
