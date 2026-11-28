import { t, type Lang } from "../i18n";

/** Static example next to the login card: what Filum does, at a glance. Not interactive. */
function CheckMarker() {
  return (
    <svg className="demo-marker" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <circle cx="12" cy="12" r="11" fill="var(--ok)" />
      <path d="M7 12.5l3.2 3.2L17 9" fill="none" stroke="var(--bg)" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ErrorMarker() {
  return (
    <svg className="demo-marker" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <rect x="5" y="5" width="14" height="14" rx="2.5" transform="rotate(45 12 12)" fill="var(--err)" />
    </svg>
  );
}

function AiMarker() {
  return (
    <svg className="demo-marker" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <circle cx="12" cy="12" r="11" fill="var(--ai)" />
      <path d="M12 5.5l1.9 4.1 4.4.5-3.3 3 .9 4.4L12 15.3l-3.9 2.2.9-4.4-3.3-3 4.4-.5z" fill="var(--bg)" />
    </svg>
  );
}

export function LoginDemo({ lang }: { lang: Lang }) {
  return (
    <section className="panel login-demo" aria-labelledby="demo-title">
      <h2 className="label" id="demo-title">{t(lang, "demo.title")}</h2>
      <p className="task demo-task">2(x + 3) = 14</p>
      <ol className="demo-thread">
        <li>
          <ErrorMarker />
          <span className="expr mono">2x + 3 = 14</span>
          <span className="badge err">{t(lang, "status.error")}</span>
        </li>
        <li>
          <AiMarker />
          <span className="demo-hint"><b>{t(lang, "demo.hint_label")}:</b> {t(lang, "demo.hint_text")}</span>
        </li>
        <li>
          <CheckMarker />
          <span className="expr mono">2x + 6 = 14</span>
          <span className="badge ok">{t(lang, "status.correct")}</span>
        </li>
      </ol>
      <p className="small soft" style={{ margin: "1rem 0 0" }}>{t(lang, "demo.caption")}</p>
    </section>
  );
}
