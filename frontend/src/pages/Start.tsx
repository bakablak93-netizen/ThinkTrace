import { useFocusOnMount } from "../components/a11y";
import { t, type Lang } from "../i18n";

export function Start({ lang, onPick, onFindError }: { lang: Lang; onPick: (demo: boolean) => void; onFindError: () => void }) {
  const heading = useFocusOnMount<HTMLHeadingElement>();
  return (
    <div className="card">
      <h2 ref={heading} tabIndex={-1}>{t(lang, "start.title")}</h2>
      <p className="muted">{t(lang, "start.topic")}</p>
      <div className="row">
        <button className="primary" onClick={() => onPick(true)}>{t(lang, "start.demo")}</button>
        <button onClick={() => onPick(false)}>{t(lang, "start.random")}</button>
        <button onClick={onFindError}>{t(lang, "start.find_error")}</button>
      </div>
    </div>
  );
}
