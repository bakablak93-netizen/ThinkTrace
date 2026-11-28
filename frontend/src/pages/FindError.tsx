import { useEffect, useRef, useState } from "react";
import { api, errorMessage, type FindErrorTask, type HintView } from "../api";
import { Formula } from "../components/Formula";
import { Logo } from "../components/Logo";
import { useFocusOnMount } from "../components/a11y";
import { useFx } from "../fx/FxProvider";
import { t, type Lang } from "../i18n";

interface Props {
  lang: Lang;
  sid: string;
  task: FindErrorTask;
  onTask: (t: FindErrorTask) => void;
  onNext: () => void;
  onReport: () => void;
  reportLabel?: string;
}

export function FindError({ lang, sid, task, onTask, onNext, onReport, reportLabel }: Props) {
  const [step, setStep] = useState<number | null>(null);
  const [bug, setBug] = useState<string | null>(null);
  const [feedback, setFeedback] = useState("");
  const [hints, setHints] = useState<HintView[]>([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const heading = useFocusOnMount<HTMLHeadingElement>(task.id);
  const fx = useFx();
  const formRef = useRef<HTMLFormElement>(null);
  const hintRef = useRef<HTMLElement>(null);
  const [shake, setShake] = useState(false);

  useEffect(() => { setStep(null); setBug(null); setFeedback(""); setHints([]); setMessage(""); }, [task.id]);

  async function check(e: React.FormEvent) {
    e.preventDefault();
    if (step === null || bug === null) return;
    setBusy(true); setMessage("");
    try {
      const r = await api.findErrorAnswer(sid, task.id, step, bug, lang);
      onTask(r.problem);
      const chosen = formRef.current?.querySelector("input[name=step]:checked")?.closest("label");
      fx.pulseFrom(chosen, r.solved ? "solved" : "err");
      if (!r.solved) { setShake(false); requestAnimationFrame(() => setShake(true)); }
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
      requestAnimationFrame(() => fx.pulseFrom(hintRef.current, "ai"));
    } catch (err) {
      setMessage(errorMessage(lang, err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="stack">
      <section aria-labelledby="fe-title">
        <h2 className="label" id="fe-title" ref={heading} tabIndex={-1}>{t(lang, "finderr.title")}</h2>
        <p className="task">{task.text.replace(/-/g, "−")}</p>
        <p className="soft" style={{ margin: "0.5rem 0 0" }}>{t(lang, "finderr.intro")}</p>
      </section>

      <form className="panel stack" onSubmit={check} ref={formRef}>
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
                {isError && <span className="badge err">{t(lang, "status.error")}</span>}
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

        <p aria-live="polite" className="msg">{feedback}</p>
        {message && <p className="msg error-text" role="alert">{message}</p>}
        {!task.solved && (
          <div className={`row${shake ? " shake" : ""}`} onAnimationEnd={() => setShake(false)}>
            <button className="btn" disabled={busy || step === null || bug === null}>{t(lang, "solve.check")}</button>
            <button type="button" className="chip" onClick={askHint} disabled={busy}>{t(lang, "solve.hint")}</button>
          </div>
        )}
      </form>

      <div aria-live="polite">
        {hints.length > 0 && (() => {
          const h = hints[hints.length - 1];
          const llm = h.source === "llm";
          return (
            <section key={hints.length} ref={hintRef} className={`hint in ${llm ? "llm" : "template"}`} aria-label={t(lang, "solve.hint")}>
              <Logo size={34} color={llm ? "var(--ai)" : "var(--soft)"} />
              <div style={{ minWidth: 0 }}>
                <div className="k">{t(lang, llm ? "hint.k_llm" : "hint.k_template", { n: h.level, total: 4 })}</div>
                <p>{h.text}</p>
              </div>
            </section>
          );
        })()}
      </div>

      {task.solved && (
        <section className="done in">
          <p className="label" style={{ color: "var(--action)" }}>{t(lang, "done.label")}</p>
          <div className="row">
            <button className="btn" onClick={onNext}>{t(lang, "finderr.next")}</button>
            <button className="chip" onClick={onReport}>{reportLabel ?? t(lang, "solve.to_report")}</button>
          </div>
        </section>
      )}
      {!task.solved && <button type="button" className="link" onClick={onReport}>{reportLabel ?? t(lang, "solve.to_report")}</button>}
    </div>
  );
}
