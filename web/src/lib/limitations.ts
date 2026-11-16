/**
 * Server limitation lines are shown to the reader, except notes written for code, such as "Local fact IDs
 * must be remapped into the run ledger before claim creation." (QA 4.5b). Newer APIs no longer send those
 * notes; the deployed API 1.4.0 still does, so the page moves them behind "Technical details".
 */
const CODE_NOTE = /\bfact IDs?\b/i;

export function splitLimitations(lines: readonly string[]): { shown: string[]; technical: string[] } {
  const shown: string[] = [], technical: string[] = [];
  for (const line of lines) (CODE_NOTE.test(line) ? technical : shown).push(line);
  return { shown, technical };
}
