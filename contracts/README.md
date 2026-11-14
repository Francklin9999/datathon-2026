# contracts/ — the shared language of the repo

Everything that crosses a boundary between two tracks is defined here: JSON shapes, HTTP endpoints, run steps, tool signatures, enumerations and reference numbers. **If two tracks disagree, this folder wins.** If this folder is wrong, fix it here first, announce it, then change code.

Owner: track **T01 (Contracts & integration)**. See `docs/04-TRACKS.md`.

## Files

| File | What it defines | Main consumers |
|---|---|---|
| `schemas.md` | Every data type exchanged over the API or stored: Profile, Portfolio, PolicyRule, Fact, Evidence, Run, Brief, WorldEvent, DatasetPassport… | Everyone |
| `api.md` | Every HTTP endpoint: method, path, request, response, errors, examples | Backend API (T03), all web tracks (T13–T15) |
| `run-events.md` | Run lifecycle, the eight step types, what each step must record, polling rules | Agents (T08), API (T03), web (T14) |
| `catalog.md` | Closed lists: metric codes, method IDs, rule IDs, limitation codes, audit check codes, error codes, theme tags | Quant (T05), rules (T06), ledger (T10), web |
| `tools.md` | Signatures of the tools agents may call (quant, data, research, world) | Agents (T08), quant (T05), research (T09), world (T11) |
| `controls.md` | Reference numbers computed from the starter data. Tests must reproduce them. | Quant (T05), optimizer (T07), rules (T06), QA (T16) |
| `fixtures/` | Example JSON payloads the frontend can build against before the backend exists | Web tracks, contract tests |

## Global conventions (apply to every payload)

1. **JSON keys are camelCase.** Python code uses snake_case internally and converts at the API boundary (Pydantic alias generator).
2. **Dates** are `YYYY-MM-DD` strings. **Timestamps** are ISO-8601 in UTC with a `Z` suffix, e.g. `2026-11-14T20:25:00Z`.
3. **Percentages are numbers in percent units**: `25.0` means 25%. Field names end in `Pct`. Percentage-point differences use unit `pts`. Fractions (0.25) never cross the API.
4. **Money** is a number plus an explicit `currency` (`"CAD"` or `"USD"`). No implicit currency anywhere.
5. **Bilingual text** is an object `{ "en": "...", "fr": "..." }` (type `I18nText`). If French is cut (D-02), `fr` repeats the English text; the key is never missing.
6. **Nulls**: a field that does not apply is `null`, not omitted, unless the schema marks it optional with `?`.
7. **IDs** follow the formats in `schemas.md` §1. IDs are opaque to the frontend except where stated.
8. **Unknown fields must be ignored** by consumers (forward compatibility). Producers must not rely on that to ship undocumented fields.
9. **Enumerations are closed.** Adding a value is a contract change (see below).

## Versioning and change process

- The API is served under `/v1`. The contract version is `contractVersion` in `GET /v1/meta`; this folder is version **1.0.0**.
- **Additive change** (new optional field, new endpoint, new enum value): edit the file, add a line to the changelog below, tell the affected tracks. Bump the minor version.
- **Breaking change** (rename, removal, type change, semantic change): needs agreement of T01 plus every consumer listed in the table above. Bump the major version. During the datathon, avoid these after Saturday night.
- Every change updates the fixtures in the same commit. A fixture that does not match `schemas.md` is a bug.

## How code mirrors the contracts

| Contract | Python (backend) | TypeScript (web) |
|---|---|---|
| `schemas.md` types | `backend/aplomb/contracts/models.py` (Pydantic v2 models, one class per type, same names) | `web/src/contracts/types.ts` (one interface per type, same names) |
| `catalog.md` enums | `backend/aplomb/contracts/catalog.py` (`StrEnum`s and constant tables) | `web/src/contracts/catalog.ts` |
| `api.md` | FastAPI routers in `backend/aplomb/api/routers/` | `web/src/api/client.ts` (one function per endpoint) |
| `fixtures/*.json` | loaded by contract tests in `backend/tests/contract/` | served by the mock client in fixture mode |

T01 writes the two mirrored files once and owns them. Other tracks import them and never redefine a type locally.

## Changelog

| Version | Date | Change |
|---|---|---|
| 1.0.0 | 2026-11-14 | First version. |

### Pre-implementation completion review (2026-11-14)

The interrupted 1.0.0 draft was completed before implementation. Corrections: baseline Mateo is insufficient without controversy evidence; profile drafts use Partial<Profile>; nullable overview risk matches missing-data behavior; batch endpoint is indexed; informational counts include flags; first-conflict boundary wording is explicit; async idempotency is session/body-scoped; polling uses completed-step watermark and indexes include session/profile version. No deployed v1 clients existed. See decision-log §6 and the per-module specs for rationale. T01 freezes mirrors against this completed 1.0.0 pack.
