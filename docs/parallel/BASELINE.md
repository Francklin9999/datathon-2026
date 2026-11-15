# Prepared shared baseline

The common branch preserves controls checkpoint `efd5ce9` plus all teammate main changes through `a9f6055`. Six merge conflicts were reconciled, retaining the new glass shell/rail, hex globe and stability/island/label improvements, backend read cache, airport/ECCC overlays, financial risk/markets navigation, native FX receipts and target allocation controls.

The merged full gate passed 852 Python tests, 16 subtests, 205 web tests and 6 infrastructure tests; static export also passed. The older controls-only 845/180 results are historical. [Merged verification and hashes](../evidence/parallel/baseline/verification.json) and [actual browser observations](../evidence/parallel/baseline/browser/README.md) distinguish successful finance/world/navigation checks from the known mobile tooltip failure.

## Known acceptance item assigned to Agent 1

At a configured 390 px mobile viewport, a hidden start-aligned information tooltip on Decision Desk extends to x=482, expanding document and innerWidth to 482. The target allocation table is properly contained in its horizontal scroll wrapper. Preserve accessible visible tooltip behavior while fixing placement and hidden-element overflow; do not hide the problem with page-wide clipping. Re-test configured screen size separately from actual innerWidth. Diagnostics and screenshots are retained in the baseline evidence directory.

## Deployment evidence boundary

Fresh public `/v1/meta` readback reports contract 1.1.0 and snapshot `snap-20261114-sourced`. The teammate's checked-in `infra/evidence/release-f098339-2026-11-15.json` records API/worker version 5 and release f098339. That file is teammate evidence, not a new independent AWS configuration read. Earlier exact version-4 records are historical. This preparation performed no deployment or production settings change. Re-discover actual release/routing/configuration before any later deployment.

The immutable-by-convention starting ref is `codex/parallel-base-20261115`; record its full SHA on worker launch. Only the returning integrator merges worker results and selects the combined contract/snapshot/release.
