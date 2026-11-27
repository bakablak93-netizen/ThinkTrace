import katex from "katex";
import "katex/dist/katex.min.css";

// LaTeX always comes from our backend printer (digits, x, operators), not raw user input.
export function Formula({ latex, display = false }: { latex: string; display?: boolean }) {
  const html = katex.renderToString(latex, { throwOnError: false, displayMode: display });
  return <span className="formula" dangerouslySetInnerHTML={{ __html: html }} />;
}
