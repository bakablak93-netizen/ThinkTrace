import { useState } from "react";
import { api, ApiError, type ProblemView } from "./api";
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

  async function run(fn: () => Promise<void>) {
    setError("");
    try {
      await fn();
    } catch (err) {
      setError(err instanceof ApiError ? t(lang, "err.generic", { code: err.code }) : t(lang, "err.network"));
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
        <select aria-label="Language" value={lang} onChange={(e) => setLang(e.target.value as Lang)}>
          <option value="ru">RU</option>
          <option value="kk">KK</option>
          <option value="en">EN</option>
        </select>
      </header>
      <main>
        {error && <p className="error">{error}</p>}
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
