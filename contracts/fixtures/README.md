# Development fixtures

These JSON files let frontend and integration tracks build before runtime services exist. They follow the wire models, but **are not captured agent runs, AWS proof, or an offline replay feature**. Keep a persistent development-fixture banner when using them. French text repeats English intentionally in these fixtures; the bilingual keys remain present.

| File | API shape | Contents |
|---|---|---|
| [profiles.json](profiles.json) | `GET /profiles` | All three complete fictional defaults, holdings and ordered rule sets |
| [run.decision.robert-tsla-25.json](run.decision.robert-tsla-25.json) | `GET /runs/{runId}` | Complete synthetic succeeded decision envelope, real data-derived numbers, two snapshots, references and illustrative audit/timeline |
| [world.events.sample.json](world.events.sample.json) | `GET /world/events` | One curated sample based on a policy-rate observation in the starter data; not a live news-feed capture |

Run fixture has `flags.fixture=true`; model strings say no model executed, times/durations/usage and steps are illustrative. It intentionally omits an optional revision and alternatives; this is an explicit pro-rata request, not automatic funding. Counted Robert checks: six conflict, one tension, one pass. Three additional informational checks appear in counts.info. Boundary 6.0 points can itself be in tension. The audit hash is recomputable over this fixture ledger; an illustrative passed report is not a statement that an LLM or Guardrail reviewed it.

World fixture geography is a display location for the Canadian central-bank observation, not an asserted impact epicenter or actual publication timestamp. The source URL identifies the observed series/date; null publishedAt is deliberate. Do not import this file into production news ingestion as a verified live story.

## Validation and ownership

T01 owns shapes and IDs; T05 owns numeric updates; module owners propose changes centrally. Run `python3 scripts/check_specs.py` from root after edits. It checks required fields, weights, rule/fact references, counts, hash and numeric controls, plus documentation links. Once T01 creates actual Pydantic/TypeScript models, contract tests must validate these payloads directly; the present integrity checker is not a replacement for generated schema validation.

Use the invalid/empty/failed cases in module test specs to construct test responses in tests, not as unlabeled production fallback. Never switch automatically from failed live service to this succeeded run.
