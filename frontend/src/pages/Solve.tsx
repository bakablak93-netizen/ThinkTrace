import { useEffect, useState } from "react";
import {
  api, errorMessage, type Confidence, type Diagnosis, type ExplainFeedback, type HintView, type ParseResult,
  type ProblemView,
} from "../api";
import { Formula } from "../components/Formula";
import { StatusChip, useFocusOnMount } from "../components/a11y";
import { t, type Lang } from "../i18n";

interface Props {
  lang: Lang;
  sid: string;
  problem: ProblemView;
  onProblem: (p: ProblemView) => void;
  onTransfer: () => void;
  onReport: () => void;
}

const CONFIDENCES: Confidence[] = ["low", "medium", "high"];

function confWord(lang: Lang, c: number): string {
  // heuristic weight from the backend, shown as a word, not a fake-precise percentage
  return t(lang, c >= 0.8 ? "conf.high" : c >= 0.4 ? "conf.medium" : "conf.low").toLowerCase();
}

export function Solve({ lang, sid, problem, onProblem, onTransfer, onReport }: Props) {
  const [text, setText] = useState("");
  const [preview, setPreview] = useState<ParseResult | null>(null);
  const [confidence, setConfidence] = useState<Confidence | null>(null);
  const [message, setMessage] = useState("");
  // diagnosis per wrong step (event id) — shown under that step
  const [diagnoses, setDiagnoses] = useState<Record<number, Diagnosis>>({});
  const [disagreed, setDisagreed] = useState<Record<number, boolean>>({});
  const [hints, setHints] = useState<HintView[]>([]);
  const [busy, setBusy] = useState(false);
  // text for screen readers: result of the last check (polite live region)
  const [announce, setAnnounce] = useState("");
  // "explain in your own words": offered after a corrected error (optional)
  const [explainFor, setExplainFor] = useState<number | null>(null);
  const [explanation, setExplanation] = useState("");
  const [feedback, setFeedback] = useState<ExplainFeedback | null>(null);
  const heading = useFocusOnMount<HTMLHeadingElement>(problem.id);
  const solvedHeading = useFocusOnMount<HTMLHeadingElement>(problem.solved);

  // reset per problem
  useEffect(() => {
    setText(""); setPreview(null); setConfidence(null); setMessage("");
    setDiagnoses({}); setDisagreed({}); setHints([]); setAnnounce("");
    setExplainFor(null); setExplanation(""); setFeedback(null);
  }, [problem.id]);

  // live preview (debounced)
  useEffect(() => {
    if (!text.trim()) { setPreview(null); return; }
    const id = setTimeout(() => {
      api.parse(text, lang).then(setPreview).catch(() => setPreview(null));
    }, 250);
    return () => clearTimeout(id);
  }, [text, lang]);

  function fail(err: unknown) {
    setMessage(errorMessage(lang, err));
  }

  async function check(e: React.FormEvent) {
    e.preventDefault();
    if (!confidence || !text.trim()) return;
    setBusy(true);
    setMessage("");
    try {
      const r = await api.step(sid, problem.id, text, confidence, lang);
      if (r.status === "parse_error") {
        setMessage(r.message ?? "");
        return;
      }
      setAnnounce(describe(r.status, text, r.diagnosis));
      setFeedback(null); setExplanation("");
      setExplainFor(r.explain && r.event_id !== undefined ? r.event_id : null);
      if (r.status === "error" && r.event_id !== undefined && r.diagnosis) {
        setDiagnoses((d) => ({ ...d, [r.event_id!]: r.diagnosis! }));
      }
      // a new episode starts after an accepted step; hints of the previous one are cleared
      if (r.status !== "error") setHints([]);
      if (r.hint) setHints([r.hint]);
      if (r.problem) onProblem(r.problem);
      setText("");
      setConfidence(null);
    } catch (err) {
      fail(err);
    } finally {
      setBusy(false);
    }
  }

  function describe(status: string, stepText: string, d?: Diagnosis): string {
    let s = `${t(lang, "solve.input")}: ${stepText} — ${t(lang, `status.${status}`)}.`;
    if (d && !d.unknown) s += ` ${t(lang, d.ambiguous ? "diag.several" : "diag.possible")} ${d.candidates.map((c) => c.name).join("; ")}.`;
    if (d?.unknown) s += ` ${t(lang, "diag.unknown")}`;
    return s;
  }

  async function sendExplanation(e: React.FormEvent) {
    e.preventDefault();
    if (explainFor === null || !explanation.trim()) return;
    setBusy(true);
    try {
      setFeedback(await api.explain(sid, problem.id, explainFor, explanation.trim(), lang));
      setExplainFor(null);
    } catch (err) {
      fail(err);
    } finally {
      setBusy(false);
    }
  }

  async function askHint() {
    setBusy(true);
    try {
      const h = await api.hint(sid, problem.id, lang);
      setHints((hs) => [...hs, h]);
    } catch (err) {
      fail(err);
    } finally {
      setBusy(false);
    }
  }

  async function disagree(eventId: number) {
    try {
      await api.disagree(sid, eventId);
      setDisagreed((d) => ({ ...d, [eventId]: true }));
    } catch (err) {
      fail(err);
    }
  }

  const isTransfer = problem.kind === "transfer";

  return (
    <div className="stack">
      <section className="card">
        <h2 className="label" ref={heading} tabIndex={-1}>{t(lang, "solve.problem")}</h2>
        {isTransfer && <div className="badge">{t(lang, "solve.transfer_badge")}</div>}
        <div className="problem"><Formula latex={problem.latex} display /></div>
      </section>

      <section className="card">
        <h2 className="label" id="steps-title">{t(lang, "solve.steps")}</h2>
        {problem.steps.length === 0 && <p className="muted">{t(lang, "solve.no_steps")}</p>}
        <ol className="steps" aria-labelledby="steps-title">
          {problem.steps.map((s) => {
            const d = diagnoses[s.event_id];
            return (
              <li key={s.event_id} className={`step ${s.status}`}>
                <div className="step-row">
                  <Formula latex={s.latex} />
                  <StatusChip lang={lang} status={s.status} />
                </div>
                {s.status === "error" && isTransfer && <p className="small muted">{t(lang, "diag.transfer_hidden")}</p>}
                {s.status === "error" && d && (
                  <div className="diag">
                    {d.unknown && <p>{t(lang, "diag.unknown")}</p>}
                    {!d.unknown && (
                      <p>
                        {t(lang, d.ambiguous ? "diag.several" : "diag.possible")}{" "}
                        {d.candidates.map((c, i) => (
                          <span key={c.bug_id}>
                            {i > 0 && "; "}<b>{c.name}</b> ({t(lang, "diag.sys_conf")}: {confWord(lang, c.confidence)})
                          </span>
                        ))}
                      </p>
                    )}
                    {d.pattern === "repeated" && <p className="small">{t(lang, "diag.repeated")}</p>}
                    <p className="small muted">{t(lang, "diag.note")}</p>
                    {disagreed[s.event_id]
                      ? <p className="small">{t(lang, "diag.disagreed")}</p>
                      : <button className="link" onClick={() => disagree(s.event_id)}
                          aria-label={`${t(lang, "diag.disagree")}: ${s.text}`}>{t(lang, "diag.disagree")}</button>}
                  </div>
                )}
              </li>
            );
          })}
        </ol>
      </section>

      <p className="sr-only" aria-live="polite">{announce}</p>
      {/* the live region stays mounted so that new hints are announced */}
      <div aria-live="polite" aria-relevant="additions text">
      {hints.length > 0 && (
        <section className="card hints" aria-label={t(lang, "solve.hint")}>
          {hints.map((h, i) => (
            <div key={i} className="hint">
              <div className="hint-head">
                <span className="label">{t(lang, "solve.hint_level", { level: h.level })}</span>
                <span className={`source ${h.source}`} title={t(lang, `hint.source_${h.source}_title`)}>
                  {t(lang, `hint.source_${h.source}`)}
                </span>
              </div>
              <p>{h.text}</p>
            </div>
          ))}
        </section>
      )}
      </div>

      {explainFor !== null && (
        <form className="card explain" onSubmit={sendExplanation} aria-labelledby="explain-title">
          <h2 className="label" id="explain-title">{t(lang, "explain.title")}</h2>
          <label htmlFor="explain-text">{t(lang, "explain.question")}</label>
          <textarea id="explain-text" value={explanation} maxLength={300} rows={3}
            onChange={(e) => setExplanation(e.target.value)} aria-describedby="explain-warning explain-count" />
          <p id="explain-warning" className="small">{t(lang, "explain.no_personal")}</p>
          <p id="explain-count" className="small muted">{explanation.length}/300</p>
          <div className="row">
            <button className="primary" disabled={busy || !explanation.trim()}>{t(lang, "explain.send")}</button>
            <button type="button" onClick={() => setExplainFor(null)}>{t(lang, "explain.skip")}</button>
          </div>
        </form>
      )}
      <div aria-live="polite">
        {feedback && (
          <section className="card explain" aria-label={t(lang, "explain.title")}>
            <div className="hint-head">
              <span className="label">{t(lang, "explain.feedback")}</span>
              <span className={`source ${feedback.source}`}>{t(lang, `explain.source_${feedback.source}`)}</span>
            </div>
            {feedback.source === "llm" ? (
              <>
                <p><b>{t(lang, "explain.correct")}</b> {feedback.correct}</p>
                <p><b>{t(lang, "explain.attention")}</b> {feedback.attention}</p>
              </>
            ) : (
              <p><b>{t(lang, "explain.compare")}</b> {feedback.rule}</p>
            )}
            <p className="small muted">{t(lang, "explain.no_grade")}</p>
          </section>
        )}
      </div>

      {problem.solved ? (
        <section className="card done">
          <h2 ref={solvedHeading} tabIndex={-1}>{t(lang, "solve.solved")}</h2>
          <div className="row">
            {!isTransfer && <button className="primary" onClick={onTransfer}>{t(lang, "solve.to_transfer")}</button>}
            <button className={isTransfer ? "primary" : ""} onClick={onReport}>{t(lang, "solve.to_report")}</button>
          </div>
        </section>
      ) : (
        <form className="card" onSubmit={check}>
          <label htmlFor="step">{t(lang, "solve.input")}</label>
          <input
            id="step" value={text} onChange={(e) => setText(e.target.value)}
            placeholder={t(lang, "solve.placeholder")} autoComplete="off" inputMode="text" maxLength={80}
          />
          <div className="preview">
            {preview?.ok && preview.latex && (<><span className="small muted">{t(lang, "solve.preview")}</span> <Formula latex={preview.latex} /></>)}
            {preview && !preview.ok && text.includes("=") && <span className="small error">{preview.message}</span>}
          </div>

          <fieldset className="confidence">
            <legend>{t(lang, "solve.confidence")}</legend>
            {CONFIDENCES.map((c) => (
              <button
                type="button" key={c} className={confidence === c ? "selected" : ""}
                aria-pressed={confidence === c} onClick={() => setConfidence(c)}
              >
                {t(lang, `conf.${c}`)}
              </button>
            ))}
          </fieldset>

          {message && <p className="error" role="alert">{message}</p>}
          <div className="row">
            <button className="primary" disabled={busy || !confidence || !text.trim()}
              title={!confidence ? t(lang, "solve.choose_confidence") : undefined}>
              {t(lang, "solve.check")}
            </button>
            {problem.hints_enabled && (
              <button type="button" onClick={askHint} disabled={busy}>{t(lang, "solve.hint")}</button>
            )}
          </div>
          {!confidence && text.trim() && <p className="small muted">{t(lang, "solve.choose_confidence")}</p>}
        </form>
      )}
      {!problem.solved && (
        <button type="button" className="link" onClick={onReport}>{t(lang, "solve.to_report")}</button>
      )}
    </div>
  );
}
