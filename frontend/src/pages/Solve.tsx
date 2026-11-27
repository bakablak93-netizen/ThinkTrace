import { useEffect, useRef, useState } from "react";
import {
  api, errorMessage, type Confidence, type Diagnosis, type ExplainFeedback, type HintView, type ParseResult,
  type ProblemView, type StepView,
} from "../api";
import { Formula } from "../components/Formula";
import { Logo } from "../components/Logo";
import { SymbolPad } from "../components/SymbolPad";
import { useFocusOnMount } from "../components/a11y";
import { useFx, type PulseKind } from "../fx/FxProvider";
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
const MAX_HINT_LEVEL = 4;

function confWord(lang: Lang, c: number): string {
  // heuristic weight from the backend, shown as a word, not a fake-precise percentage
  return t(lang, c >= 0.8 ? "conf.high" : c >= 0.4 ? "conf.medium" : "conf.low").toLowerCase();
}

/** Thread shown while solving: accepted steps + the latest error that is not corrected yet.
 *  (A corrected error disappears from the thread here, as in the prototype; the report keeps it.) */
export function visibleThread(steps: StepView[]): StepView[] {
  const out: StepView[] = [];
  for (const s of steps) {
    while (out.length && out[out.length - 1].status === "error") out.pop();
    out.push(s);
  }
  return out;
}

const NODE: Record<string, string> = { correct: "ok", solved: "solved", error: "err" };

export function Solve({ lang, sid, problem, onProblem, onTransfer, onReport }: Props) {
  const fx = useFx();
  const [text, setText] = useState("");
  const [preview, setPreview] = useState<ParseResult | null>(null);
  const [confidence, setConfidence] = useState<Confidence | null>(null);
  const [message, setMessage] = useState("");
  const [diagnoses, setDiagnoses] = useState<Record<number, Diagnosis>>({});
  const [disagreed, setDisagreed] = useState<Record<number, boolean>>({});
  const [hint, setHint] = useState<HintView | null>(null);
  const [hintSeq, setHintSeq] = useState(0);         // re-mounts the hint card -> slide-in on every show
  const [busy, setBusy] = useState(false);
  const [announce, setAnnounce] = useState("");
  const [explainFor, setExplainFor] = useState<number | null>(null);
  const [explanation, setExplanation] = useState("");
  const [feedback, setFeedback] = useState<ExplainFeedback | null>(null);
  const [fresh, setFresh] = useState<number | null>(null);   // only the newest step animates
  const [shake, setShake] = useState(false);
  const pendingPulse = useRef<{ id: number; kind: PulseKind } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const hintRef = useRef<HTMLElement>(null);
  const threadRef = useRef<HTMLOListElement>(null);
  const heading = useFocusOnMount<HTMLHeadingElement>(problem.id);

  useEffect(() => {
    setText(""); setPreview(null); setConfidence(null); setMessage("");
    setDiagnoses({}); setDisagreed({}); setHint(null); setAnnounce("");
    setExplainFor(null); setExplanation(""); setFeedback(null); setFresh(null);
  }, [problem.id]);

  // live preview (debounced)
  useEffect(() => {
    if (!text.trim()) { setPreview(null); return; }
    const id = setTimeout(() => { api.parse(text, lang).then(setPreview).catch(() => setPreview(null)); }, 250);
    return () => clearTimeout(id);
  }, [text, lang]);

  // FX for a checked step: pulse from its marker once it is rendered
  useEffect(() => {
    const p = pendingPulse.current;
    if (!p) return;
    pendingPulse.current = null;
    const node = threadRef.current?.querySelector(`[data-step="${p.id}"] .node`);
    fx.pulseFrom(node ?? inputRef.current, p.kind);
  }, [problem, fx]);

  // FX for a hint: blue wave from the card
  useEffect(() => { if (hintSeq > 0) fx.pulseFrom(hintRef.current, "ai"); }, [hintSeq, fx]);

  const thread = visibleThread(problem.steps);
  const last = thread[thread.length - 1];
  const fixing = last?.status === "error";
  const isTransfer = problem.kind === "transfer";

  function fail(err: unknown) {
    setMessage(errorMessage(lang, err));
  }

  function doShake() {
    setShake(false);
    requestAnimationFrame(() => setShake(true));
  }

  function showHint(h: HintView) {
    setHint(h);
    setHintSeq((n) => n + 1);
  }

  async function check(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) { setMessage(t(lang, "solve.empty")); doShake(); return; }
    if (!confidence) { setMessage(t(lang, "solve.choose_confidence")); doShake(); return; }
    setBusy(true);
    setMessage("");
    try {
      const r = await api.step(sid, problem.id, text, confidence, lang);
      if (r.status === "parse_error") {
        setMessage(r.message ?? "");
        doShake();
        fx.pulseFrom(inputRef.current, "err");
        return;
      }
      setAnnounce(describe(r.status, text, r.diagnosis));
      setFeedback(null); setExplanation("");
      setExplainFor(r.explain && r.event_id !== undefined ? r.event_id : null);
      if (r.event_id !== undefined) {
        setFresh(r.event_id);
        pendingPulse.current = { id: r.event_id, kind: r.status === "error" ? "err" : r.status === "solved" ? "solved" : "ok" };
      }
      if (r.status === "error") {
        doShake();
        if (r.event_id !== undefined && r.diagnosis) setDiagnoses((d) => ({ ...d, [r.event_id!]: r.diagnosis! }));
      } else {
        setHint(null);   // a new episode starts after an accepted step
      }
      if (r.hint) showHint(r.hint);
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
      showHint(await api.hint(sid, problem.id, lang));
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

  function onInput(v: string) {
    setText(v);
    fx.energy(0.35);
    const r = inputRef.current?.getBoundingClientRect();
    if (r) fx.pulse(r.left + 30 + Math.random() * Math.max(10, r.width - 60), r.top + r.height / 2, "key");
  }

  const errorEvent = fixing ? last.event_id : null;
  const hintIsLlm = hint?.source === "llm";

  return (
    <div className="stack">
      <section aria-labelledby="task-label">
        <h2 className="label" id="task-label" ref={heading} tabIndex={-1}>
          {t(lang, "solve.task_label")}{isTransfer && <span className="soft"> · {t(lang, "solve.transfer_badge")}</span>}
        </h2>
        <p className="task">{problem.text.replace(/-/g, "−")}</p>
      </section>

      {/* polite live region stays mounted; the card inside re-mounts on every hint (slide-in) */}
      <div aria-live="polite">
        {hint && (
          <section key={hintSeq} ref={hintRef} className={`hint in ${hintIsLlm ? "llm" : "template"}`}
            aria-label={t(lang, "solve.hint")}>
            <Logo size={34} color={hintIsLlm ? "var(--ai)" : "var(--soft)"} />
            <div style={{ minWidth: 0 }}>
              <div className="k">
                {t(lang, hintIsLlm ? "hint.k_llm" : "hint.k_template", { n: hint.level, total: MAX_HINT_LEVEL })}
              </div>
              <p>{hint.text}</p>
              <div className="row">
                {problem.hints_enabled && !problem.solved && (
                  <button className="chip" type="button" onClick={askHint} disabled={busy || hint.level >= MAX_HINT_LEVEL}>
                    {t(lang, "hint.more")}
                  </button>
                )}
                {errorEvent !== null && (disagreed[errorEvent]
                  ? <span className="small soft">{t(lang, "diag.disagreed")}</span>
                  : <button className="link" type="button" onClick={() => disagree(errorEvent)}>{t(lang, "diag.disagree")}</button>)}
              </div>
            </div>
          </section>
        )}
      </div>

      <section className="panel" aria-labelledby="steps-title">
        <h2 className="label" id="steps-title">{t(lang, "solve.steps")}</h2>
        <ol className="thread" ref={threadRef}>
          {thread.map((s, i) => {
            const d = diagnoses[s.event_id];
            const kind = NODE[s.status];
            const badge = s.status === "error" ? t(lang, "status.error") : t(lang, `status.${s.status}`);
            return (
              <li key={s.event_id} data-step={s.event_id} className={`step${fresh === s.event_id ? " fresh" : ""}`}>
                <span className={`node ${kind}`} aria-hidden="true" />
                <span className="sr-only">{t(lang, "finderr.step_n", { n: i + 1 })}: </span>
                <span className="expr"><Formula latex={s.latex} /></span>
                <span className={`badge ${kind}`}>{badge}</span>
                {s.status === "error" && isTransfer && <p className="diag">{t(lang, "diag.transfer_hidden")}</p>}
                {s.status === "error" && d && (
                  <div className="diag">
                    {d.unknown ? <p>{t(lang, "diag.unknown")}</p> : (
                      <p>
                        {t(lang, d.ambiguous ? "diag.several" : "diag.possible")}{" "}
                        {d.candidates.map((c, k) => (
                          <span key={c.bug_id}>
                            {k > 0 && "; "}<b>{c.name}</b> ({t(lang, "diag.sys_conf")}: {confWord(lang, c.confidence)})
                          </span>
                        ))}
                      </p>
                    )}
                    {d.pattern === "repeated" && <p>{t(lang, "diag.repeated")}</p>}
                    <p className="small muted">{t(lang, "diag.note")}</p>
                  </div>
                )}
              </li>
            );
          })}

          {!problem.solved && (
            <li className="step">
              <span className="node next" aria-hidden="true" />
              <form onSubmit={check} noValidate>
                <div className="ask">
                  {fixing ? t(lang, "solve.ask_fix", { n: thread.length }) : t(lang, "solve.ask_next", { n: thread.length + 1 })}
                </div>
                <label htmlFor="step" className="sub">{t(lang, fixing ? "solve.sub_fix" : "solve.sub_next")}</label>
                <div className={`row${shake ? " shake" : ""}`} onAnimationEnd={() => setShake(false)}>
                  <input id="step" ref={inputRef} className="field" type="text" value={text} maxLength={80}
                    onChange={(e) => onInput(e.target.value)} placeholder={t(lang, "solve.placeholder")}
                    autoComplete="off" inputMode="text" spellCheck={false} aria-describedby="step-msg step-preview" />
                  <button className="btn" type="submit" disabled={busy}>{t(lang, "solve.check")}</button>
                </div>
                <SymbolPad lang={lang} inputRef={inputRef} value={text} onChange={onInput} />
                <div className="preview" id="step-preview">
                  {preview?.ok && preview.latex && (<><span className="small muted">{t(lang, "solve.preview")}</span> <Formula latex={preview.latex} /></>)}
                  {preview && !preview.ok && text.includes("=") && <span className="small error-text">{preview.message}</span>}
                </div>
                <div className="row" role="group" aria-labelledby="conf-label" style={{ marginTop: "1rem" }}>
                  <span id="conf-label" className="soft" style={{ fontSize: "0.9375rem" }}>{t(lang, "solve.confidence")}</span>
                  {CONFIDENCES.map((c) => (
                    <button key={c} type="button" className="chip" aria-pressed={confidence === c} onClick={() => setConfidence(c)}>
                      {t(lang, `solve.conf_${c}`)}
                    </button>
                  ))}
                </div>
                <p className="msg" id="step-msg" role="status">{message}</p>
                {problem.hints_enabled && !hint && (
                  <button type="button" className="chip" onClick={askHint} disabled={busy}>{t(lang, "solve.hint")}</button>
                )}
              </form>
            </li>
          )}
        </ol>
      </section>

      <p className="sr-only" aria-live="polite">{announce}</p>

      {explainFor !== null && (
        <form className="panel" onSubmit={sendExplanation} aria-labelledby="explain-title">
          <h2 className="label" id="explain-title">{t(lang, "explain.title")}</h2>
          <label htmlFor="explain-text" className="sub">{t(lang, "explain.question")}</label>
          <textarea id="explain-text" className="field" value={explanation} maxLength={300} rows={3}
            onChange={(e) => setExplanation(e.target.value)} aria-describedby="explain-warning explain-count" />
          <p id="explain-warning" className="small soft">{t(lang, "explain.no_personal")}</p>
          <p id="explain-count" className="small muted">{explanation.length}/300</p>
          <div className="row">
            <button className="btn" disabled={busy || !explanation.trim()}>{t(lang, "explain.send")}</button>
            <button type="button" className="chip" onClick={() => setExplainFor(null)}>{t(lang, "explain.skip")}</button>
          </div>
        </form>
      )}
      <div aria-live="polite">
        {feedback && (
          <section className={`hint in ${feedback.source === "llm" ? "llm" : "template"}`} aria-label={t(lang, "explain.title")}>
            <Logo size={34} color={feedback.source === "llm" ? "var(--ai)" : "var(--soft)"} />
            <div style={{ minWidth: 0 }}>
              <div className="k">{t(lang, "explain.feedback")} · {t(lang, `explain.source_${feedback.source}`)}</div>
              {feedback.source === "llm" ? (
                <>
                  <p><b>{t(lang, "explain.correct")}</b> {feedback.correct}</p>
                  <p><b>{t(lang, "explain.attention")}</b> {feedback.attention}</p>
                </>
              ) : (
                <p><b>{t(lang, "explain.compare")}</b> {feedback.rule}</p>
              )}
              <p className="small muted" style={{ fontWeight: 400, fontSize: "0.875rem" }}>{t(lang, "explain.no_grade")}</p>
            </div>
          </section>
        )}
      </div>

      {problem.solved ? (
        <SolvedBlock lang={lang} answer={last?.text ?? ""} isTransfer={isTransfer} onTransfer={onTransfer} onReport={onReport} />
      ) : (
        <button type="button" className="link" onClick={onReport}>{t(lang, "solve.to_report")}</button>
      )}
    </div>
  );
}

function SolvedBlock({ lang, answer, isTransfer, onTransfer, onReport }: {
  lang: Lang; answer: string; isTransfer: boolean; onTransfer: () => void; onReport: () => void;
}) {
  const heading = useFocusOnMount<HTMLHeadingElement>();
  return (
    <section className="done in" aria-labelledby="done-title">
      <div>
        <h2 className="label" id="done-title" ref={heading} tabIndex={-1}>{t(lang, "done.label")}</h2>
        <b>{answer.replace(/-/g, "−")}</b>
      </div>
      <div className="row">
        {!isTransfer && <button className="btn" type="button" onClick={onTransfer}>{t(lang, "solve.to_transfer")}</button>}
        <button className={isTransfer ? "btn" : "chip"} type="button" onClick={onReport}>{t(lang, "solve.to_report")}</button>
      </div>
    </section>
  );
}
