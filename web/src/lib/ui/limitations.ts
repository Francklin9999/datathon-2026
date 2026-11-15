/** Deduplicate limitation codes (first occurrence wins) and split them into shown / folded. */
export function splitLimitations(codes: readonly string[], compactAfter: number | undefined): { shown: string[]; folded: string[] } {
  const unique = [...new Set(codes)];
  if (compactAfter === undefined) return { shown: unique, folded: [] };
  return { shown: unique.slice(0, compactAfter), folded: unique.slice(compactAfter) };
}
