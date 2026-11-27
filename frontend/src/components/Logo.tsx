/** Filum thread logo (SVG from the prototype). Amber in the header, blue in AI hints,
 *  neutral for template hints. Decorative: always aria-hidden. */
export function Logo({ size = 30, color = "var(--action)" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" focusable="false" style={{ flex: "none" }}>
      <path d="M3 22 C9 22 11 10 16 10 S23 22 29 22" fill="none" stroke={color} strokeWidth="3.2" strokeLinecap="round" />
      <circle cx="16" cy="10" r="3" fill="var(--err)" />
    </svg>
  );
}
