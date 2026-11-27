import { useFocusOnMount } from "../components/a11y";
import { t, type Lang } from "../i18n";

export function Start({ lang, onPick, onFindError }: { lang: Lang; onPick: (demo: boolean) => void; onFindError: () => void }) {
  const heading = useFocusOnMount<HTMLHeadingElement>();
  return (
    <div className="panel">
      <h2 className="label" ref={heading} tabIndex={-1}>{t(lang, "start.title")}</h2>
      <p className="ask" style={{ marginTop: 0 }}>{t(lang, "start.topic")}</p>
      <div className="row">
        <button className="btn" onClick={() => onPick(true)}>{t(lang, "start.demo")}</button>
        <button className="chip" onClick={() => onPick(false)}>{t(lang, "start.random")}</button>
        <button className="chip" onClick={onFindError}>{t(lang, "start.find_error")}</button>
      </div>
    </div>
  );
}
