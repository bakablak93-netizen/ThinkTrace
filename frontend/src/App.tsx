import { useEffect, useState } from "react";
import {
  api, errorMessage, type BankLevel, type FindErrorTask, type PilotNext, type ProblemView, type StartResult,
} from "./api";
import { Logo } from "./components/Logo";
import { FontSizeControl } from "./components/a11y";
import { t, type Lang } from "./i18n";
import { readPilotCode } from "./pilot";
import { Consent } from "./pages/Consent";
import { ExamProblem } from "./pages/ExamProblem";
import { FindError } from "./pages/FindError";
import { Login } from "./pages/Login";
import { Report } from "./pages/Report";
import { Solve } from "./pages/Solve";
import { Start } from "./pages/Start";

type Screen = "login" | "consent" | "start" | "solve" | "find_error" | "exam" | "report";

export default function App() {
  const [lang, setLang] = useState<Lang>("ru");
  // pilot link /?pilot=CODE (invalid codes are ignored): consent screen instead of the nickname
  const [pilotCode] = useState(() => readPilotCode());
  const [pilot, setPilot] = useState<PilotNext | null>(null);
  const [screen, setScreen] = useState<Screen>(pilotCode ? "consent" : "login");
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

  // pilot: next pre/post problem, practice, or the end (individual report only)
  const pilotAdvance = (post = false, sessionId = sid) => run(async () => {
    const r = await api.pilotNext(sessionId, post);
    setPilot(r);
    if (r.problem) { setProblem(r.problem); setScreen("exam"); }
    else if (r.phase === "practice") { setProblem(null); setScreen("start"); }
    else if (r.phase === "done") { await api.finish(sessionId); setScreen("report"); }
  });
  const onPilotStarted = (r: StartResult) => {
    setSid(r.session_id); setToken(r.token);
    pilotAdvance(false, r.session_id);   // state updates are async: pass the id explicitly
  };
  const inPractice = pilot?.phase === "practice";

  const pick = (demo: boolean) => run(async () => {
    setProblem(await api.newProblem(sid, demo));
    setScreen("solve");
  });
  // problem bank: first problem of a level, or the next one after the current problem
  const pickLevel = (level: BankLevel, after?: string | null) => run(async () => {
    setProblem(await api.newProblem(sid, false, level, after));
    setScreen("solve");
  });
  const deleteMyData = () => run(async () => {
    if (!window.confirm(t(lang, "delete.confirm"))) return;
    await api.deleteMyData(sid, token);
    setSid(""); setToken(""); setProblem(null); setFindTask(null); setPilot(null);
    setNotice(t(lang, "delete.done"));
    setScreen(pilotCode ? "consent" : "login");
  });
  const toFindError = () => run(async () => {
    setFindTask(await api.findError(sid, lang));
    setScreen("find_error");
  });
  const toTransfer = () => run(async () => setProblem(await api.transfer(sid)));
  const toReport = () => run(async () => {
    if (pilot) { setScreen("start"); return; }   // pilot: the report comes after the post-test
    await api.finish(sid);
    setScreen("report");
  });

  // header tag: "Problem 1 of 2" (main), "2 of 2" (final / transfer), or the mode name
  const tag = pilot && pilot.phase !== "done" ? t(lang, `pilot.tag_${pilot.phase}`)
    : screen === "solve" && problem ? t(lang, "tag.task", { n: problem.kind === "transfer" ? 2 : 1, total: 2 })
    : screen === "find_error" ? t(lang, "finderr.title") : null;

  return (
    <div className="page">
      <header className="app-header">
        <h1 className="brand">
          <Logo />
          {t(lang, "app.title")}
          {tag && <span className="tag">{tag}</span>}
        </h1>
        <div className="tools">
          <FontSizeControl lang={lang} />
          <select className="icon" aria-label={t(lang, "a11y.language")} value={lang}
            onChange={(e) => setLang(e.target.value as Lang)}>
            <option value="ru">RU</option>
            <option value="kk">KK</option>
            <option value="en">EN</option>
          </select>
        </div>
      </header>
      <main className="stack">
        {error && <p className="msg error-text" role="alert">{error}</p>}
        {screen === "consent" && pilotCode && (
          <>
            {notice && <p className="hint" role="status" style={{ display: "block" }}>{notice}</p>}
            <Consent lang={lang} cohort={pilotCode} onStarted={onPilotStarted} />
          </>
        )}
        {screen === "exam" && problem && pilot && (
          <ExamProblem lang={lang} sid={sid} problem={problem} index={pilot.index ?? 1} total={pilot.total ?? 3}
            onProblem={setProblem} onDone={() => pilotAdvance()} />
        )}
        {inPractice && screen !== "exam" && (
          <section className="done" aria-label={t(lang, "pilot.tag_practice")}>
            <p className="soft" style={{ margin: 0 }}>{t(lang, "pilot.practice_note")}</p>
            <button className="btn" type="button" onClick={() => pilotAdvance(true)}>{t(lang, "pilot.to_post")}</button>
          </section>
        )}
        {screen === "login" && (
          <Login lang={lang} notice={notice}
            onDone={(id, tok) => { setSid(id); setToken(tok); setNotice(""); setScreen("start"); }} />
        )}
        {screen === "start" && <Start lang={lang} onPick={pick} onLevel={(lv) => pickLevel(lv)} onFindError={toFindError} />}
        {screen === "find_error" && findTask && (
          <FindError lang={lang} sid={sid} task={findTask} onTask={setFindTask}
            onNext={toFindError} onReport={toReport} reportLabel={pilot ? t(lang, "pilot.back_to_practice") : undefined} />
        )}
        {screen === "solve" && problem && (
          <Solve lang={lang} sid={sid} problem={problem} onProblem={setProblem}
            onTransfer={toTransfer} onReport={toReport}
            reportLabel={pilot ? t(lang, "pilot.back_to_practice") : undefined}
            onNext={problem.level ? () => pickLevel(problem.level!, problem.bank_id) : undefined} />
        )}
        {screen === "report" && (
          <Report lang={lang} sid={sid}
            onRestart={() => { setProblem(null); setPilot(null); setSid(""); setScreen(pilotCode ? "consent" : "login"); }}
            onDelete={deleteMyData} />
        )}
      </main>
      {screen !== "login" && screen !== "report" && sid && (
        <section className="row" aria-label={t(lang, "delete.button")}>
          <button type="button" className="link danger" onClick={deleteMyData}>{t(lang, "delete.button")}</button>
          <span className="small muted">{t(lang, "delete.explain")}</span>
        </section>
      )}
      <footer><p className="foot">{t(lang, "foot.note")}</p></footer>
    </div>
  );
}
