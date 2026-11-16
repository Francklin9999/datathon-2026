// Pure helpers for the issuer relationship panel (features/markets/IssuerEvidence.tsx).

/**
 * Edge source ids whose raw GLEIF page the backend keeps for the owning session and serves
 * from GET /intelligence/relationships/captures/{sha256}: Level 2 pages (gleif_relations.capture_l2)
 * and exact ISIN/LEI pair pages (exact.capture_pair). Other sources, e.g. the indexed N-PORT
 * holdings transcript, carry a hash but are not served by that route.
 */
const SERVED_CAPTURE_SOURCES = new Set(['entity_gleif_level2', 'entity_gleif_isin_lei']);

const SHA256 = /^[0-9a-f]{64}$/;

export const isCaptureHash = (hash: unknown): hash is string => typeof hash === 'string' && SHA256.test(hash);

/** The hash to offer for raw download, or null when the route cannot serve it. */
export function servedCaptureHash(sourceId: string | null | undefined, hash: string | null | undefined): string | null {
  return sourceId && SERVED_CAPTURE_SOURCES.has(sourceId) && isCaptureHash(hash) ? hash : null;
}

export const capturePath = (sha256: string) => `/intelligence/relationships/captures/${sha256}`;

export type GoldenCopySource = {
  url: string; content_sha256: string; retrieved_at: string; licence: string;
  content_as_of?: string | null; licence_url?: string | null;
};
export type GoldenCopyRecord = {
  legalName: string | null; jurisdiction: string | null; entityStatus: string | null;
  source: GoldenCopySource; datasetVersion: string;
};

type NodeLike = { label?: string | null; attributes?: Record<string, unknown>; annotations?: unknown[] };

const text = (v: unknown): string | null => (typeof v === 'string' && v ? v : null);
const record = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);

/**
 * The GLEIF Golden Copy enrichment that relationship_graph.relationship_view adds to an exact LEI
 * node (annotation kind 'golden_copy_entity' plus golden_* attributes), or null when absent.
 * When present the node label is the Golden Copy legal name.
 */
export function goldenCopyRecord(node: NodeLike | undefined): GoldenCopyRecord | null {
  if (!node) return null;
  const notes = (node.annotations ?? []).filter(a => record(a) && a.kind === 'golden_copy_entity') as Record<string, unknown>[];
  const note = notes[notes.length - 1];
  if (!note || !record(note.source)) return null;
  const s = note.source;
  const url = text(s.url); const sha = text(s.content_sha256); const retrieved = text(s.retrieved_at); const licence = text(s.licence);
  const version = text(note.dataset_version);
  if (!url || !sha || !retrieved || !licence || !version) return null;
  const attrs = node.attributes ?? {};
  return {
    legalName: text(node.label), jurisdiction: text(attrs.golden_jurisdiction), entityStatus: text(attrs.golden_entity_status),
    source: { url, content_sha256: sha, retrieved_at: retrieved, licence, content_as_of: text(s.content_as_of), licence_url: text(s.licence_url) },
    datasetVersion: version,
  };
}
