# Codex-3 completion verification — 2026-11-15

Branch: `codex/agent-2-research-audit`. Continued from `729d510` after reading the actual `.codex-3` session. Its latest request was to make the connected-source workflows pass end to end. This continuation does not merge or deploy the three parallel branches.

## Completed changes

- Gave each Japanese/Korean research form its own React-generated field IDs so labels resolve to the correct form when both are mounted.
- Displayed the regional source response hashes and optional company-response hash with the existing capture provenance.
- Documented the three registered connected-market routes in the API route table; documented the existing rebalance run variants and priority bounds; regenerated the schema specification hashes.
- Corrected the existing Northern Trust classification test fixture to return the requested NTRS ticker, preserving the provider's strict identity check.
- Ignored isolated `.next-*` output directories and removed temporary build-directory entries from the tracked TypeScript configuration.

## Verification

`UV_CACHE_DIR=/tmp/aplomb-agent-2-uv-cache npm run check` exited 0:

- Generated contract/schema/source-directory checks and Ruff: PASS.
- Python: 922 passed, 16 subtests passed; one existing Mangum event-loop deprecation warning.
- TypeScript: PASS.
- Web contract/unit tests: 205 passed.
- Specification verification: 128 documents, three fixtures and 20 acceptance rows passed.
- Infrastructure: six tests passed and CDK synthesis completed. No infrastructure was applied.

`NEXT_PUBLIC_APLOMB_API_BASE=http://127.0.0.1:8102/v1 APLOMB_NEXT_DIST_DIR=.next npm run build:web` exited 0 and exported all 13 static pages.

Browser evidence contains 18 passing cases with real configured providers, without fixture replacements. The twelve connected stock/chain account cases are retained from codex-3's preceding final run. All six regional cases were rerun in this continuation against the local static export and real API: Japan prices/company/financials and Korea filings/financials/ownership. No browser runtime exceptions were recorded. Ownership completed after a longer provider response; no timeout or fabricated replacement was used.

A fresh 390-pixel mobile inspection found document width 390, two regional forms, zero duplicate IDs and zero unmatched regional labels. The screenshot shows the actual forms after dismissing onboarding. Changed files and retained evidence were compared against local credential values without printing those values: zero credential matches. `git diff --check` passed.

Evidence: `docs/evidence/parallel/agent-2/final-verification/` contains gate/build logs, browser case summary, regional replay output, mobile assertions, screenshot and SHA-256 manifest. Raw credential-bearing configuration and local application state remain ignored.

Local verification: PASS. Deployment/combined-branch acceptance: not performed and outside this continuation. Existing broader research/history limitations and the FRED/ALFRED permission blocker remain documented in REQUIREMENTS.md and BLOCKERS.md.
