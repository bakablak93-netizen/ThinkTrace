import { t, type Lang } from "../i18n";

export function Start({ lang, onPick }: { lang: Lang; onPick: (demo: boolean) => void }) {
  return (
    <div className="card">
      <h2>{t(lang, "start.title")}</h2>
      <p className="muted">{t(lang, "start.topic")}</p>
      <div className="row">
        <button className="primary" onClick={() => onPick(true)}>{t(lang, "start.demo")}</button>
        <button onClick={() => onPick(false)}>{t(lang, "start.random")}</button>
      </div>
    </div>
  );
}
