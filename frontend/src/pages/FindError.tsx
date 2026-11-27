import { useEffect, useState } from "react";
import { api, errorMessage, type FindErrorTask, type HintView } from "../api";
import { Formula } from "../components/Formula";
import { useFocusOnMount } from "../components/a11y";
import { t, type Lang } from "../i18n";

interface Props {
  lang: Lang;
  sid: string;
  task: FindErrorTask;
  onTask: (t: FindErrorTask) => void;
  onNext: () => void;
  onReport: () => void;
}

export function FindError({ lang, sid, task, onTask, onNext, onReport }: Props) {
  const [step, setStep] = useState<number | null>(null);
  const [bug, setBug] = useState<string | null>(null);
  const [feedback, setFeedback] = useState("");
  const [hints, setHints] = useState<HintView[]>([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const heading = useFocusOnMount<HTMLHeadingElement>(task.id);

  useEffect(() => { setStep(null); setBug(null); setFeedback(""); setHints([]); setMessage(""); }, [task.id]);

  async function check(e: React.FormEvent) {
    e.preventDefault();
    if (step === null || bug === null) return;
    setBusy(true); setMessage("");
    try {
      const r = await api.findErrorAnswer(sid, task.id, step, bug, lang);
      onTask(r.problem);
      if (r.solved) {
        const name = r.problem.options.find((o) => o.bug_id === bug)?.name ?? "";
        setFeedback(t(lang, "finderr.solved", { n: step + 1, name }));
      } else if (!r.step_correct) setFeedback(t(lang, "finderr.wrong_step"));
      else setFeedback(t(lang, "finderr.wrong_type"));
    } catch (err) {
      setMessage(errorMessage(lang, err));
    } finally {
      setBusy(false);
    }
  }

  async function askHint() {
    setBusy(true);
    try {
      const h = await api.findErrorHint(sid, task.id, lang);
      setHints((hs) => [...hs, h]);
    } catch (err) {
      setMessage(errorMessage(lang, err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="stack">
      <section className="card">
        <h2 ref={heading} tabIndex={-1}>{t(lang, "finderr.title")}</h2>
        <p className="muted">{t(lang, "finderr.intro")}</p>
        <div className="problem"><Formula latex={task.latex} display /></div>
      </section>

      <form className="card stack" onSubmit={check}>
        <fieldset className="choices">
          <legend>{t(lang, "finderr.which_step")}</legend>
          {task.steps.map((s) => {
            const isError = task.solved && task.error_index === s.index;
            return (
              <label key={s.index} className={`choice ${step === s.index ? "selected" : ""} ${isError ? "error" : ""}`}>
                <input type="radio" name="step" value={s.index} checked={step === s.index}
                  onChange={() => setStep(s.index)} disabled={task.solved} />
                <span className="choice-n">{t(lang, "finderr.step_n", { n: s.index + 1 })}</span>
                <Formula latex={s.latex} />
                {isError && <span className="chip error"><span aria-hidden="true">✗ </span>{t(lang, "status.error")}</span>}
              </label>
            );
          })}
        </fieldset>

        <fieldset className="choices">
          <legend>{t(lang, "finderr.which_type")}</legend>
          {task.options.map((o) => (
            <label key={o.bug_id} className={`choice ${bug === o.bug_id ? "selected" : ""}`}>
              <input type="radio" name="bug" value={o.bug_id} checked={bug === o.bug_id}
                onChange={() => setBug(o.bug_id)} disabled={task.solved} />
              <span>{o.name}</span>
            </label>
          ))}
        </fieldset>

        <p aria-live="polite" className={feedback && !task.solved ? "error" : ""}>{feedback}</p>
        {message && <p className="error" role="alert">{message}</p>}
        {!task.solved && (
          <div className="row">
            <button className="primary" disabled={busy || step === null || bug === null}>{t(lang, "solve.check")}</button>
            <button type="button" onClick={askHint} disabled={busy}>{t(lang, "solve.hint")}</button>
          </div>
        )}
      </form>

      <div aria-live="polite">
        {hints.length > 0 && (
          <section className="card hints" aria-label={t(lang, "solve.hint")}>
            {hints.map((h, i) => (
              <div key={i} className="hint">
                <div className="hint-head">
                  <span className="label">{t(lang, "solve.hint_level", { level: h.level })}</span>
                  <span className={`source ${h.source}`}>{t(lang, `hint.source_${h.source}`)}</span>
                </div>
                <p>{h.text}</p>
              </div>
            ))}
          </section>
        )}
      </div>

      {task.solved && (
        <section className="card done">
          <div className="row">
            <button className="primary" onClick={onNext}>{t(lang, "finderr.next")}</button>
            <button onClick={onReport}>{t(lang, "solve.to_report")}</button>
          </div>
        </section>
      )}
      {!task.solved && <button type="button" className="link" onClick={onReport}>{t(lang, "solve.to_report")}</button>}
    </div>
  );
}
