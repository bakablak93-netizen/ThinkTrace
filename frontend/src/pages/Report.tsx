import { useEffect, useState } from "react";
import { api, errorMessage, type Independence, type Report as ReportData, type ReportProblem } from "../api";
import { StatusChip, useFocusOnMount } from "../components/a11y";
import { t, type Lang } from "../i18n";

function mmss(sec: number) {
  const s = Math.max(0, Math.round(sec));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function IndexBlock({ lang, ix }: { lang: Lang; ix: Independence }) {
  const pct = (v: number) => `${Math.round(v * 100)}%`;
  return (
    <section className="card" aria-labelledby="index-title">
      <h3 id="index-title" className="label">{t(lang, "index.title")}</h3>
      <p className="index-value">
        {ix.value}<span className="small muted"> / 100</span>
        {ix.partial && <span className="small muted"> — {t(lang, "index.partial")}</span>}
      </p>
      <ul>
        <li>{t(lang, "index.hints", { n: ix.hints_requested, v: pct(ix.hints_component) })}</li>
        <li>{t(lang, "index.attempts", { ok: ix.steps_correct, total: ix.steps_total, v: pct(ix.attempts_component) })}</li>
        <li>{ix.transfer_component === null ? t(lang, "index.transfer_none")
          : t(lang, "index.transfer", { v: pct(ix.transfer_component) })}</li>
      </ul>
      <details>
        <summary>{t(lang, "index.how")}</summary>
        <p className="small">{t(lang, "index.formula")}</p>
      </details>
      <p className="small muted">{t(lang, "index.not_grade")}</p>
    </section>
  );
}

function FindErrorBlock({ lang, p }: { lang: Lang; p: ReportProblem }) {
  return (
    <section className="card">
      <h3 className="label">{t(lang, "finderr.title")}</h3>
      <p className="mono">{p.text}{!p.solved && <span className="chip error">{t(lang, "report.unsolved")}</span>}</p>
      <p>{t(lang, "finderr.report", { tries: p.answers.length, hints: p.hints.length })}</p>
      <ol>
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

function ProblemBlock({ lang, p }: { lang: Lang; p: ReportProblem }) {
  if (p.kind === "find_error") return <FindErrorBlock lang={lang} p={p} />;
  return (
    <section className="card">
      <div className="label">{t(lang, p.kind === "main" ? "report.main" : "report.transfer")}</div>
      <h3 className="mono">{p.text}{!p.solved && <span className="chip error">{t(lang, "report.unsolved")}</span>}</h3>
      <div className="table-wrap" tabIndex={0} role="region"
        aria-label={`${t(lang, p.kind === "main" ? "report.main" : "report.transfer")}: ${t(lang, "report.step")}`}>
        <table>
          <thead>
            <tr>
              <th scope="col">{t(lang, "report.step")}</th>
              <th scope="col">{t(lang, "report.result")}</th>
              <th scope="col">{t(lang, "report.error_type")}</th>
              <th scope="col">{t(lang, "report.self_conf")}</th>
            </tr>
          </thead>
          <tbody>
            {p.steps.map((s) => (
              <tr key={s.event_id}>
                <td className="mono">{s.text}</td>
                <td><StatusChip lang={lang} status={s.status} /></td>
                <td>
                  {s.status === "error" && (s.unknown ? "—" : s.bugs.map((b) => b.name).join(" / "))}
                  {s.disagreed && <span> ⚑ <span className="sr-only">{t(lang, "report.disagreed")}</span></span>}
                </td>
                <td>{t(lang, `conf.${s.self_confidence}`)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {Object.keys(p.errors_by_bug).length > 0 && (
        <>
          <div className="label">{t(lang, "report.errors_by_type")}</div>
          <ul>{Object.entries(p.errors_by_bug).map(([name, n]) => <li key={name}>{name}: {n}</li>)}</ul>
        </>
      )}
    </section>
  );
}

export function Report({ lang, sid, onRestart }: { lang: Lang; sid: string; onRestart: () => void }) {
  const [data, setData] = useState<ReportData | null>(null);
  const [error, setError] = useState("");
  const heading = useFocusOnMount<HTMLHeadingElement>(data !== null);

  useEffect(() => {
    api.report(sid, lang).then(setData).catch((err) => setError(errorMessage(lang, err)));
  }, [sid, lang]);

  if (error) return <p className="error" role="alert">{error}</p>;
  if (!data) return null;
  const tot = data.totals;

  return (
    <div className="stack">
      <section className="card">
        <h2 ref={heading} tabIndex={-1}>{t(lang, "report.title")}</h2>
        <p>{data.summary}</p>
        <p>{data.transfer.text}</p>
        <div className="tiles">
          {([["report.steps", tot.steps], ["report.errors", tot.errors], ["report.hints", tot.hints],
             ["report.corrections", tot.corrections], ["report.disagreements", tot.disagreements]] as const).map(([k, v]) => (
            <div className="tile" key={k}><div className="tile-v">{v}</div><div className="small muted">{t(lang, k)}</div></div>
          ))}
        </div>
        <p className="small muted">{data.note}</p>
      </section>

      {data.independence && <IndexBlock lang={lang} ix={data.independence} />}
      {data.problems.map((p) => <ProblemBlock key={p.id} lang={lang} p={p} />)}

      <section className="card">
        <div className="label">{t(lang, "report.timeline")}</div>
        <ol className="timeline">
          {data.timeline.map((e, i) => (
            <li key={i} className={e.status ?? e.type}>
              <span className="mono small muted">{mmss(e.t)}</span>{" "}
              {t(lang, `tl.${e.type}`, { level: e.level ?? "" })}
              {e.text && <span className="mono"> {e.text}</span>}
              {e.status && <StatusChip lang={lang} status={e.status} />}
              {e.auto && <span className="small muted"> ({t(lang, "report.auto")})</span>}
              {e.source && <span className={`source ${e.source}`}>{t(lang, `hint.source_${e.source}`)}</span>}
            </li>
          ))}
        </ol>
      </section>

      <button onClick={onRestart}>{t(lang, "report.new")}</button>
    </div>
  );
}
