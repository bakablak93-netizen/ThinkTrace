import type { BankLevel } from "../api";
import { useFocusOnMount } from "../components/a11y";
import { t, type Lang } from "../i18n";

const LEVELS: BankLevel[] = ["A", "B", "C"];

export function Start({ lang, onPick, onLevel, onFindError }: {
  lang: Lang; onPick: (demo: boolean) => void; onLevel: (level: BankLevel) => void; onFindError: () => void;
}) {
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
      <h3 className="label" id="levels-title" style={{ marginTop: "1.5rem" }}>{t(lang, "start.levels")}</h3>
      <ul className="list-plain" aria-labelledby="levels-title" style={{ marginTop: "0.75rem" }}>
        {LEVELS.map((lv) => (
          <li key={lv} className="row">
            <button className="chip" onClick={() => onLevel(lv)}>{t(lang, "start.level_btn", { level: lv })}</button>
            <span className="soft">{t(lang, `start.level_${lv}`)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
