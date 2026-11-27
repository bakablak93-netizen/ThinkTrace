import { useEffect, useState } from "react";
import {
  api, ApiError, type Confidence, type Diagnosis, type HintView, type ParseResult, type ProblemView,
} from "../api";
import { Formula } from "../components/Formula";
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

  // reset per problem
  useEffect(() => {
    setText(""); setPreview(null); setConfidence(null); setMessage("");
    setDiagnoses({}); setDisagreed({}); setHints([]);
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
    setMessage(err instanceof ApiError ? t(lang, "err.generic", { code: err.code }) : t(lang, "err.network"));
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
        <div className="label">{t(lang, "solve.problem")}</div>
        {isTransfer && <div className="badge">{t(lang, "solve.transfer_badge")}</div>}
        <div className="problem"><Formula latex={problem.latex} display /></div>
      </section>

      <section className="card">
        <div className="label">{t(lang, "solve.steps")}</div>
        {problem.steps.length === 0 && <p className="muted">{t(lang, "solve.no_steps")}</p>}
        <ol className="steps">
          {problem.steps.map((s) => {
            const d = diagnoses[s.event_id];
            return (
              <li key={s.event_id} className={`step ${s.status}`}>
                <div className="step-row">
                  <Formula latex={s.latex} />
                  <span className={`chip ${s.status}`}>{t(lang, `status.${s.status}`)}</span>
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
                      : <button className="link" onClick={() => disagree(s.event_id)}>{t(lang, "diag.disagree")}</button>}
                  </div>
                )}
              </li>
            );
          })}
        </ol>
      </section>

      {hints.length > 0 && (
        <section className="card hints" aria-live="polite">
          {hints.map((h, i) => (
            <div key={i} className="hint">
              <div className="label">{t(lang, "solve.hint_level", { level: h.level })}</div>
              <p>{h.text}</p>
            </div>
          ))}
        </section>
      )}

      {problem.solved ? (
        <section className="card done">
          <h2>{t(lang, "solve.solved")}</h2>
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

          {message && <p className="error">{message}</p>}
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
