/** Split a formatted figure into characters; only ASCII digits roll, signs/separators stay put. */
export interface RollSegment { ch: string; digit: boolean }

export function rollSegments(text: string): RollSegment[] {
  return Array.from(text, ch => ({ ch, digit: ch >= '0' && ch <= '9' }));
}
