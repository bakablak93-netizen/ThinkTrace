import { useRef, useState } from "react";
import { api, errorMessage, type Confidence, type ProblemView } from "../api";
import { Formula } from "../components/Formula";
import { SymbolPad } from "../components/SymbolPad";
import { useFocusOnMount } from "../components/a11y";
import { useFx } from "../fx/FxProvider";
import { t, type Lang } from "../i18n";

const CONFIDENCES: Confidence[] = ["low", "medium", "high"];

/** Pilot pre/post test problem: no hints and NO feedback on correctness. Lines are only
 *  "recorded"; no ok/err/solved effects either (they would give the answer away). */
export function ExamProblem({ lang, sid, problem, index, total, onProblem, onDone }: {
  lang: Lang; sid: string; problem: ProblemView; index: number; total: number;
  onProblem: (p: ProblemView) => void; onDone: () => void;
}) {
  const fx = useFx();
  const [text, setText] = useState("");
  const [confidence, setConfidence] = useState<Confidence | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const heading = useFocusOnMount<HTMLHeadingElement>(problem.id);
  const phaseKey = problem.phase === "post" ? "exam.post" : "exam.pre";

  async function record(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) { setMessage(t(lang, "solve.empty")); return; }
    if (!confidence) { setMessage(t(lang, "solve.choose_confidence")); return; }
    setBusy(true);
    setMessage("");
    try {
      const r = await api.step(sid, problem.id, text, confidence, lang);
      if (r.status === "parse_error") { setMessage(r.message ?? ""); return; }
      if (r.problem) onProblem(r.problem);
      setText("");
      setConfidence(null);
      setMessage(t(lang, "exam.recorded"));
      if (r.finished) onDone();
    } catch (err) {
      setMessage(errorMessage(lang, err));
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    if (!window.confirm(t(lang, "exam.submit_confirm"))) return;
    setBusy(true);
    try {
      await api.finishExam(sid, problem.id);
      onDone();
    } catch (err) {
      setMessage(errorMessage(lang, err));
    } finally {
      setBusy(false);
    }
  }

  function onInput(v: string) {
    setText(v);
    fx.energy(0.35);
    const r = inputRef.current?.getBoundingClientRect();
    if (r) fx.pulse(r.left + r.width / 2, r.top + r.height / 2, "key");
  }

  return (
    <div className="stack">
      <section aria-labelledby="exam-title">
        <h2 className="label" id="exam-title" ref={heading} tabIndex={-1}>
          {t(lang, phaseKey)} · {t(lang, "exam.problem_n", { n: index, total })}
        </h2>
        <p className="task">{problem.text.replace(/-/g, "−")}</p>
        <p className="soft" style={{ margin: "0.5rem 0 0" }}>{t(lang, "exam.note")}</p>
      </section>

      <section className="panel" aria-labelledby="exam-steps">
        <h2 className="label" id="exam-steps">{t(lang, "solve.steps")}</h2>
        <ol className="thread">
          {problem.steps.map((s, i) => (
            <li key={s.event_id} className="step">
              <span className="node rec" aria-hidden="true" />
              <span className="sr-only">{t(lang, "finderr.step_n", { n: i + 1 })}: </span>
              <span className="expr"><Formula latex={s.latex} /></span>
              <span className="badge rec">{t(lang, "exam.recorded_badge")}</span>
            </li>
          ))}
          <li className="step">
            <span className="node next" aria-hidden="true" />
            <form onSubmit={record} noValidate>
              <div className="ask">{t(lang, "solve.ask_next", { n: problem.steps.length + 1 })}</div>
              <label htmlFor="exam-step" className="sub">{t(lang, "solve.sub_next")}</label>
              <div className="row">
                <input id="exam-step" ref={inputRef} className="field" type="text" value={text} maxLength={80}
                  onChange={(e) => onInput(e.target.value)} placeholder={t(lang, "solve.placeholder")}
                  autoComplete="off" spellCheck={false} aria-describedby="exam-msg" />
                <button className="btn" type="submit" disabled={busy}>{t(lang, "exam.record")}</button>
              </div>
              <SymbolPad lang={lang} inputRef={inputRef} value={text} onChange={onInput} />
              <div className="row" role="group" aria-labelledby="exam-conf" style={{ marginTop: "1rem" }}>
                <span id="exam-conf" className="soft">{t(lang, "solve.confidence")}</span>
                {CONFIDENCES.map((c) => (
                  <button key={c} type="button" className="chip" aria-pressed={confidence === c} onClick={() => setConfidence(c)}>
                    {t(lang, `solve.conf_${c}`)}
                  </button>
                ))}
              </div>
              <p className="msg" id="exam-msg" role="status">{message}</p>
            </form>
          </li>
        </ol>
      </section>
      <div className="row">
        <button type="button" className="chip" onClick={submit} disabled={busy}>{t(lang, "exam.submit")}</button>
        <span className="small soft">{t(lang, "exam.submit_hint")}</span>
      </div>
    </div>
  );
}
