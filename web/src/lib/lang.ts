import { useState } from "react";
import { deviceLang } from "./i18n";
import { LANGS, type Lang } from "./types";

const KEY = "pip:lang";

/** Each viewer picks their own language (mixed rooms: DE / EN / VI side by side) and it stays on this device. */
export function useLang(): [Lang, (l: Lang) => void] {
  const [lang, setLang] = useState<Lang>(() => {
    try {
      const v = localStorage.getItem(KEY) as Lang | null;
      return v && LANGS.includes(v) ? v : deviceLang();
    } catch {
      return deviceLang();
    }
  });
  const set = (l: Lang) => {
    setLang(l);
    try {
      localStorage.setItem(KEY, l);
    } catch {
      /* private mode: this page only */
    }
  };
  return [lang, set];
}
