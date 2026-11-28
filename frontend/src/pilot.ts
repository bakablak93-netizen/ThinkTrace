/** Pilot link: /?pilot=CODE. Codes that do not match the regex are ignored (normal mode). */
export const COHORT_RE = /^[A-Za-z0-9_-]{1,24}$/;

export function readPilotCode(search: string = window.location.search): string | null {
  const code = new URLSearchParams(search).get("pilot");
  return code && COHORT_RE.test(code) ? code : null;
}
