/** Runtime validation for caller-supplied model input (the advanced JSON of a conditional policy). */
const object = (v: unknown): v is Record<string, unknown> =>
  v !== null && typeof v === 'object' && !Array.isArray(v);

/** Parse data only; no executable user code is accepted. */
export function parseModelInput(text: string): Record<string, unknown> {
  if (new TextEncoder().encode(text).length > 240_000) throw new Error('Input exceeds 240 kB');
  const value: unknown = JSON.parse(text);
  if (!object(value)) throw new Error('Input must be a JSON object');
  return value;
}
