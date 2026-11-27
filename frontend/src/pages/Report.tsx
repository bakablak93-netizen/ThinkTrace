import { useEffect, useState } from "react";
import { api, errorMessage, type Independence, type Report as ReportData, type ReportProblem, type ReportStep } from "../api";
import { StatusChip, useFocusOnMount } from "../components/a11y";
import { t, type Lang } from "../i18n";

const NODE: Record<string, string> = { correct: "ok", solved: "solved", error: "err" };

function mmss(sec: number) {
  const s = Math.max(0, Math.round(sec));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

const pretty = (s: string) => s.replace(/-/g, "−");

/** Full solution thread of a problem (in the report errors stay visible). */
function Thread({ lang, steps }: { lang: Lang; steps: ReportStep[] }) {
  if (!steps.length) return <p className="soft">{t(lang, "solve.no_steps")}</p>;
  return (
    <ol className="thread">
      {steps.map((s, i) => (
        <li key={s.event_id} className="step">
          <span className={`node ${NODE[s.status]}`} aria-hidden="true" />
          <span className="sr-only">{t(lang, "finderr.step_n", { n: i + 1 })}: </span>
          <span className="expr mono">{pretty(s.text)}</span>
          <StatusChip lang={lang} status={s.status} />
          <p className="diag small">
            {t(lang, "report.self_conf_short", { v: t(lang, `conf.${s.self_confidence}`).toLowerCase() })}
            {s.disagreed && <> · {t(lang, "report.disagreed")}</>}
          </p>
        </li>
      ))}
    </ol>
  );
}

function IndexDetails({ lang, ix }: { lang: Lang; ix: Independence }) {
  const pct = (v: number) => `${Math.round(v * 100)}%`;
  return (
    <details>
      <summary>{t(lang, "index.title")}: {t(lang, "index.how").toLowerCase()}</summary>
      <ul className="soft">
        <li>{t(lang, "index.hints", { n: ix.hints_requested, v: pct(ix.hints_component) })}</li>
        <li>{t(lang, "index.attempts", { ok: ix.steps_correct, total: ix.steps_total, v: pct(ix.attempts_component) })}</li>
        <li>{ix.transfer_component === null ? t(lang, "index.transfer_none")
          : t(lang, "index.transfer", { v: pct(ix.transfer_component) })}</li>
      </ul>
      <p className="small soft">{t(lang, "index.formula")}</p>
      {ix.partial && <p className="small soft">{t(lang, "index.partial")}</p>}
      <p className="small muted">{t(lang, "index.not_grade")}</p>
    </details>
  );
}

function FindErrorBlock({ lang, p }: { lang: Lang; p: ReportProblem }) {
  return (
    <section className="panel" aria-label={t(lang, "finderr.title")}>
      <h3 className="label">{t(lang, "finderr.title")}</h3>
      <p className="expr mono">{pretty(p.text)}{!p.solved && <span className="badge err">{t(lang, "report.unsolved")}</span>}</p>
      <p className="soft">{t(lang, "finderr.report", { tries: p.answers.length, hints: p.hints.length })}</p>
      <ol className="soft">
        {p.answers.map((a, i) => (
          <li key={i}>
            {t(lang, "finderr.step_n", { n: a.step_index + 1 })}:{" "}
            {t(lang, a.step_correct ? "finderr.step_ok" : "finderr.step_bad")},{" "}
            {t(lang, a.type_correct ? "finderr.type_ok" : "finderr.type_bad")}
          </li>
        ))}
      </ol>
    </section>
  );
}

export function Report({ lang, sid, onRestart, onDelete }: {
  lang: Lang; sid: string; onRestart: () => void; onDelete: () => void;
}) {
  const [data, setData] = useState<ReportData | null>(null);
  const [error, setError] = useState("");
  const heading = useFocusOnMount<HTMLHeadingElement>(data !== null);

  useEffect(() => {
    api.report(sid, lang).then(setData).catch((err) => setError(errorMessage(lang, err)));
  }, [sid, lang]);

  if (error) return <p className="msg error-text" role="alert">{error}</p>;
  if (!data) return null;

  const main = data.problems.filter((p) => p.kind === "main");
  const final = data.problems.filter((p) => p.kind === "transfer").slice(-1)[0];
  const findErr = data.problems.filter((p) => p.kind === "find_error");
  const mainSteps = main.flatMap((p) => p.steps);
  const errors = mainSteps.filter((s) => s.status === "error");
  const ix = data.independence;
  const stats: [string, string | number][] = [
    ["report.stat_steps", data.totals.steps],
    ["report.stat_errors", data.totals.errors],
    ["report.stat_hints", data.totals.hints],
    ["report.stat_index", ix ? ix.value : "—"],
  ];

  return (
    <div className="stack">
      <section aria-labelledby="report-title">
        <h2 className="label" id="report-title" ref={heading} tabIndex={-1}>{t(lang, "report.title")}</h2>
        <p className="ask" style={{ margin: 0 }}>{data.summary}</p>
      </section>

      <ul className="stats list-plain" aria-label={t(lang, "report.title")}>
        {stats.map(([k, v]) => (
          <li key={k} className="stat"><b>{v}</b><span>{t(lang, k)}</span></li>
        ))}
      </ul>
      {ix && <IndexDetails lang={lang} ix={ix} />}

      {main.map((p) => (
        <section key={p.id} className="panel" aria-label={t(lang, "report.thread")}>
          <h3 className="label">{t(lang, "report.thread")}</h3>
          <p className="task" style={{ fontSize: "clamp(1.75rem, 6vw, 2.5rem)", marginBottom: "1.25rem" }}>{pretty(p.text)}</p>
          <Thread lang={lang} steps={p.steps} />
        </section>
      ))}

      <section className="panel" aria-labelledby="where-title">
        <h3 className="label" id="where-title">{t(lang, "report.where_error")}</h3>
        {errors.length === 0 ? <p className="soft">{t(lang, "report.no_errors")}</p> : (
          <ul className="list-plain">
            {errors.map((s) => (
              <li key={s.event_id}>
                <span className="expr mono">{pretty(s.text)}</span> <span className="badge err">{t(lang, "status.error")}</span>
                <p className="diag">
                  {s.unknown ? t(lang, "report.unknown_type") : s.bugs.map((b) => b.name).join(" / ")}
                  {s.pattern === "repeated" && <> · {t(lang, "diag.repeated")}</>}
                </p>
              </li>
            ))}
          </ul>
        )}
        <p className="small muted">{data.note}</p>
      </section>

      <section className="done" aria-labelledby="final-title">
        <div>
          <h3 className="label" id="final-title">{t(lang, "report.final")}</h3>
          {final && <b>{pretty(final.text)}</b>}
          <p className="soft" style={{ margin: "0.375rem 0 0" }}>{data.transfer.text}</p>
        </div>
      </section>
      {final && final.steps.length > 0 && (
        <section className="panel" aria-label={t(lang, "report.final")}>
          <Thread lang={lang} steps={final.steps} />
        </section>
      )}

      {findErr.map((p) => <FindErrorBlock key={p.id} lang={lang} p={p} />)}

      <details className="panel">
        <summary>{t(lang, "report.timeline")}</summary>
        <ol className="timeline">
          {data.timeline.map((e, i) => (
            <li key={i}>
              <span className="mono small muted">{mmss(e.t)}</span>{" "}
              {t(lang, `tl.${e.type}`, { level: e.level ?? "" })}
              {e.text && <span className="mono"> {pretty(e.text)}</span>}
              {e.status && <> <StatusChip lang={lang} status={e.status} /></>}
              {e.auto && <span className="small muted"> ({t(lang, "report.auto")})</span>}
              {e.source && <span className="small muted"> · {t(lang, `hint.source_${e.source}`)}</span>}
            </li>
          ))}
        </ol>
      </details>

      <div className="row">
        <button className="btn" type="button" onClick={onRestart}>{t(lang, "report.new")}</button>
        <button className="link danger" type="button" onClick={onDelete}>{t(lang, "delete.button")}</button>
      </div>
      <p className="small muted">{t(lang, "delete.explain")}</p>
    </div>
  );
}
