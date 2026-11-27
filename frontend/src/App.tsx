import { useEffect, useState } from "react";
import { api, errorMessage, type FindErrorTask, type ProblemView } from "./api";
import { FontSizeControl } from "./components/a11y";
import { t, type Lang } from "./i18n";
import { FindError } from "./pages/FindError";
import { Login } from "./pages/Login";
import { Report } from "./pages/Report";
import { Solve } from "./pages/Solve";
import { Start } from "./pages/Start";

type Screen = "login" | "start" | "solve" | "find_error" | "report";

export default function App() {
  const [lang, setLang] = useState<Lang>("ru");
  const [screen, setScreen] = useState<Screen>("login");
  const [sid, setSid] = useState("");
  const [token, setToken] = useState("");   // kept only in memory, needed to delete my data
  const [notice, setNotice] = useState("");
  const [problem, setProblem] = useState<ProblemView | null>(null);
  const [findTask, setFindTask] = useState<FindErrorTask | null>(null);
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
  const deleteMyData = () => run(async () => {
    if (!window.confirm(t(lang, "delete.confirm"))) return;
    await api.deleteMyData(sid, token);
    setSid(""); setToken(""); setProblem(null); setFindTask(null);
    setNotice(t(lang, "delete.done"));
    setScreen("login");
  });
  const toFindError = () => run(async () => {
    setFindTask(await api.findError(sid, lang));
    setScreen("find_error");
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
        {screen === "login" && (
          <Login lang={lang} notice={notice}
            onDone={(id, tok) => { setSid(id); setToken(tok); setNotice(""); setScreen("start"); }} />
        )}
        {screen === "start" && <Start lang={lang} onPick={pick} onFindError={toFindError} />}
        {screen === "find_error" && findTask && (
          <FindError lang={lang} sid={sid} task={findTask} onTask={setFindTask}
            onNext={toFindError} onReport={toReport} />
        )}
        {screen === "solve" && problem && (
          <Solve lang={lang} sid={sid} problem={problem} onProblem={setProblem}
            onTransfer={toTransfer} onReport={toReport} />
        )}
        {screen === "report" && <Report lang={lang} sid={sid} onRestart={() => { setProblem(null); setScreen("login"); }} />}
      </main>
      {screen !== "login" && sid && (
        <footer>
          <p className="small muted">{t(lang, "delete.explain")}</p>
          <button type="button" className="danger" onClick={deleteMyData}>{t(lang, "delete.button")}</button>
        </footer>
      )}
    </div>
  );
}
