/**
 * Which page section the section dock highlights (scroll spy). Pure; the dock measures the boxes.
 *
 * A section chosen in the dock stays active while any of it is on screen (the dock clears the choice
 * as soon as the person scrolls by hand): side-by-side neighbours, a short section the next one
 * overtakes at the reading line, or the last rows that can never reach it cannot steal it. Without a
 * choice, the active row is the lowest row of sections whose top has passed the reading line; side by
 * side sections share a row and the first wins. At the bottom of the page, the last section.
 */
export interface SectionBox { id: string; top: number; bottom: number }

/** Tops within this many pixels belong to the same row. */
const SAME_ROW_PX = 8;

export function activeSection(boxes: readonly SectionBox[], opts: {
  /** Reading line, in viewport pixels from the top. */
  line: number;
  viewportHeight: number;
  atBottom: boolean;
  /** Last section chosen in the dock, if any. */
  preferred: string | null;
}): string | null {
  if (boxes.length === 0) return null;
  const preferred = opts.preferred ? boxes.find(b => b.id === opts.preferred) : undefined;
  if (preferred && preferred.top < opts.viewportHeight && preferred.bottom > 0) return preferred.id;
  if (opts.atBottom) return boxes[boxes.length - 1]!.id;
  const passed = boxes.filter(b => b.top <= opts.line);
  if (passed.length === 0) return boxes[0]!.id;
  const rowTop = Math.max(...passed.map(b => b.top));
  return passed.find(b => rowTop - b.top <= SAME_ROW_PX)!.id;
}
