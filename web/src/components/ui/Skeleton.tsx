/** Shimmering placeholder (styles/components.css `.skeleton`); purely visual, hidden from assistive tech. */
export function Skeleton({ width = '100%', height = 14 }: { width?: number | string; height?: number | string }) {
  return <span className="skeleton" aria-hidden="true" style={{ width, height }} />;
}
