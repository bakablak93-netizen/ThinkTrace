import { useState } from "react";
import { api, errorMessage, type StartResult } from "../api";
import { t, type Lang } from "../i18n";

/** Pilot consent: shown before anything is stored. Start only after the explicit checkbox. */
export function Consent({ lang, cohort, onStarted }: {
  lang: Lang; cohort: string; onStarted: (r: StartResult) => void;
}) {
  const [agreed, setAgreed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function start(e: React.FormEvent) {
    e.preventDefault();
    if (!agreed) return;
    setBusy(true);
    setError("");
    try {
      onStarted(await api.startPilot(cohort, lang));
    } catch (err) {
      setError(errorMessage(lang, err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="panel" onSubmit={start} aria-labelledby="consent-title">
      <h2 className="ask" id="consent-title" style={{ marginTop: 0 }}>{t(lang, "consent.title")}</h2>
      <p>{t(lang, "consent.what_is")}</p>
      <h3 className="label">{t(lang, "consent.collect_h")}</h3>
      <p>{t(lang, "consent.collect")}</p>
      <h3 className="label">{t(lang, "consent.not_collect_h")}</h3>
      <p>{t(lang, "consent.not_collect")}</p>
      <h3 className="label">{t(lang, "consent.why_h")}</h3>
      <p>{t(lang, "consent.why")}</p>
      <h3 className="label">{t(lang, "consent.how_h")}</h3>
      <p>{t(lang, "consent.how")}</p>
      <h3 className="label">{t(lang, "consent.delete_h")}</h3>
      <p>{t(lang, "consent.delete")}</p>
      <p className="hint" style={{ display: "block" }}><b>{t(lang, "consent.minor")}</b></p>
      <p className="soft">{t(lang, "consent.voluntary")}</p>
      <label className="choice" htmlFor="consent-box">
        <input id="consent-box" type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
        <span>{t(lang, "consent.checkbox")}</span>
      </label>
      {error && <p className="msg error-text" role="alert">{error}</p>}
      <div className="row" style={{ marginTop: "1rem" }}>
        <button className="btn" type="submit" disabled={!agreed || busy}>{t(lang, "consent.start")}</button>
      </div>
    </form>
  );
}
