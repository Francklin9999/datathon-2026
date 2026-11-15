/** Shimmering placeholder (styles/components.css `.skeleton`); purely visual, hidden from assistive tech. */
export function Skeleton({ width = '100%', height = 14, radius }: { width?: number | string; height?: number | string; radius?: number }) {
  return <span className="skeleton" aria-hidden="true" style={{ width, height, ...(radius === undefined ? {} : { borderRadius: radius }) }} />;
}
