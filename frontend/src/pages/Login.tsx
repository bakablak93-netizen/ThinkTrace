import { useState } from "react";
import { api, ApiError } from "../api";
import { useFocusOnMount } from "../components/a11y";
import { t, type Lang } from "../i18n";

export function Login({ lang, onDone, notice }: { lang: Lang; onDone: (sid: string, token: string) => void; notice?: string }) {
  const [nick, setNick] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const heading = useFocusOnMount<HTMLHeadingElement>();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const r = await api.start(nick.trim(), lang);
      onDone(r.session_id, r.token);
    } catch (err) {
      const code = err instanceof ApiError ? err.code : "network";
      setError(code === "bad_nickname" || code === "http_422" ? t(lang, "err.bad_nickname") : t(lang, "err.network"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card" onSubmit={submit} aria-labelledby="login-title">
      <h2 id="login-title" ref={heading} tabIndex={-1}>{t(lang, "login.title")}</h2>
      {notice && <p className="notice" role="status">{notice}</p>}
      <p className="muted">{t(lang, "app.tagline")}</p>
      <label htmlFor="nick">{t(lang, "login.nick")}</label>
      <input id="nick" value={nick} onChange={(e) => setNick(e.target.value)} maxLength={24}
        aria-describedby="nick-hint" autoComplete="off" />
      <p id="nick-hint" className="small muted">{t(lang, "login.nick_hint")}</p>
      {error && <p className="error" role="alert">{error}</p>}
      <button className="primary" disabled={busy || nick.trim().length < 2}>{t(lang, "login.go")}</button>
    </form>
  );
}
