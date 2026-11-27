import { useState } from "react";
import { api, ApiError } from "../api";
import { t, type Lang } from "../i18n";

export function Login({ lang, onDone }: { lang: Lang; onDone: (sid: string) => void }) {
  const [nick, setNick] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const r = await api.start(nick.trim(), lang);
      onDone(r.session_id);
    } catch (err) {
      const code = err instanceof ApiError ? err.code : "network";
      setError(code === "bad_nickname" || code === "http_422" ? t(lang, "err.bad_nickname") : t(lang, "err.network"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card" onSubmit={submit}>
      <p className="muted">{t(lang, "app.tagline")}</p>
      <label htmlFor="nick">{t(lang, "login.nick")}</label>
      <input id="nick" value={nick} onChange={(e) => setNick(e.target.value)} maxLength={24} autoFocus />
      <p className="small muted">{t(lang, "login.nick_hint")}</p>
      {error && <p className="error">{error}</p>}
      <button className="primary" disabled={busy || nick.trim().length < 2}>{t(lang, "login.go")}</button>
    </form>
  );
}
