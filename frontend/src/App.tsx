import { useState } from "react";
import { t, type Lang } from "./i18n";

// Screens (stage 1+): Login -> ModeSelect -> Solve -> Report -> Transfer.
export default function App() {
  const [lang, setLang] = useState<Lang>("ru");
  return (
    <main>
      <h1>{t(lang, "app.title")}</h1>
      <select value={lang} onChange={(e) => setLang(e.target.value as Lang)}>
        <option value="ru">RU</option>
        <option value="kk">KK</option>
        <option value="en">EN</option>
      </select>
    </main>
  );
}
