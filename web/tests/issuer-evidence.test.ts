import assert from 'node:assert/strict';
import test from 'node:test';
import { capturePath, goldenCopyRecord, isCaptureHash, servedCaptureHash } from '../src/lib/issuerEvidence';

const SHA = 'a'.repeat(64);

test('raw capture download is offered only for GLEIF sources the capture route serves', () => {
  assert.equal(servedCaptureHash('entity_gleif_level2', SHA), SHA);
  assert.equal(servedCaptureHash('entity_gleif_isin_lei', SHA), SHA);
  // The indexed N-PORT transcript carries a hash but is not stored as a session capture.
  assert.equal(servedCaptureHash('fund_sec_nport_indexed_excerpt', SHA), null);
  assert.equal(servedCaptureHash('entity_gleif_level2', null), null);
  assert.equal(servedCaptureHash('entity_gleif_level2', 'A'.repeat(64)), null);
  assert.equal(servedCaptureHash(null, SHA), null);
  assert.equal(isCaptureHash('abc'), false);
  assert.equal(capturePath(SHA), `/intelligence/relationships/captures/${SHA}`);
});

test('Golden Copy enrichment on an LEI node is read with its provenance', () => {
  // Shape produced by relationship_graph.relationship_view (add_node golden_* attributes + annotate).
  const node = {
    id: 'lei:010CMKZ3VON21WF2ZD45', kind: 'entity', label: 'Example Golden Name',
    attributes: { jurisdiction: 'FR', golden_jurisdiction: 'FR', golden_entity_status: 'ACTIVE' },
    annotations: [
      { type: 'none_published', level: 'direct' },
      { kind: 'golden_copy_entity', dataset_version: 'gleif-golden-0123456789abcdef',
        source: { url: 'https://leidata-preview.gleif.org/x.zip', content_sha256: SHA, metadata_sha256: 'b'.repeat(64),
          content_as_of: '2026-11-15T08:00:00+00:00', retrieved_at: '2026-11-15T09:00:00+00:00',
          available_at: '2026-11-15T09:00:00+00:00', published_at: null,
          licence: 'GLEIF LEI access service data CC0 1.0', licence_url: 'https://www.gleif.org/en/meta/lei-data-terms-of-use' } },
    ],
  };
  const golden = goldenCopyRecord(node);
  assert.ok(golden);
  assert.equal(golden.legalName, 'Example Golden Name');
  assert.equal(golden.jurisdiction, 'FR');
  assert.equal(golden.entityStatus, 'ACTIVE');
  assert.equal(golden.source.content_sha256, SHA);
  assert.equal(golden.datasetVersion, 'gleif-golden-0123456789abcdef');
});

test('nodes without a complete Golden Copy annotation show nothing', () => {
  assert.equal(goldenCopyRecord(undefined), null);
  assert.equal(goldenCopyRecord({ label: 'X', attributes: {}, annotations: [{ type: 'none_published', level: 'direct' }] }), null);
  assert.equal(goldenCopyRecord({ label: 'X', attributes: {}, annotations: [{ kind: 'golden_copy_entity', source: { url: 'https://x' } }] }), null);
});
