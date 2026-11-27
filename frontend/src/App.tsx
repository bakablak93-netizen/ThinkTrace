import { useEffect, useState } from "react";
import { api, errorMessage, type ProblemView } from "./api";
import { FontSizeControl } from "./components/a11y";
import { t, type Lang } from "./i18n";
import { Login } from "./pages/Login";
import { Report } from "./pages/Report";
import { Solve } from "./pages/Solve";
import { Start } from "./pages/Start";

type Screen = "login" | "start" | "solve" | "report";

export default function App() {
  const [lang, setLang] = useState<Lang>("ru");
  const [screen, setScreen] = useState<Screen>("login");
  const [sid, setSid] = useState("");
  const [problem, setProblem] = useState<ProblemView | null>(null);
  const [error, setError] = useState("");

  useEffect(() => { document.documentElement.lang = lang; }, [lang]);

  async function run(fn: () => Promise<void>) {
    setError("");
    try {
      await fn();
    } catch (err) {
      setError(errorMessage(lang, err));
    }
  }

  const pick = (demo: boolean) => run(async () => {
    setProblem(await api.newProblem(sid, demo));
    setScreen("solve");
  });
  const toTransfer = () => run(async () => setProblem(await api.transfer(sid)));
  const toReport = () => run(async () => {
    await api.finish(sid);
    setScreen("report");
  });

  return (
    <div className="app">
      <header>
        <h1>{t(lang, "app.title")}</h1>
        <div className="header-tools">
          <FontSizeControl lang={lang} />
          <select aria-label={t(lang, "a11y.language")} value={lang} onChange={(e) => setLang(e.target.value as Lang)}>
            <option value="ru">RU — Русский</option>
            <option value="kk">KK — Қазақша</option>
            <option value="en">EN — English</option>
          </select>
        </div>
      </header>
      <main>
        {error && <p className="error" role="alert">{error}</p>}
        {screen === "login" && <Login lang={lang} onDone={(id) => { setSid(id); setScreen("start"); }} />}
        {screen === "start" && <Start lang={lang} onPick={pick} />}
        {screen === "solve" && problem && (
          <Solve lang={lang} sid={sid} problem={problem} onProblem={setProblem}
            onTransfer={toTransfer} onReport={toReport} />
        )}
        {screen === "report" && <Report lang={lang} sid={sid} onRestart={() => { setProblem(null); setScreen("login"); }} />}
      </main>
    </div>
  );
}
