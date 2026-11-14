# 05 — Implementation conventions

## Contracts and naming

Wire JSON is camelCase, Python internals snake_case, TS keys mirror JSON. Pydantic aliases are the only boundary conversion. Enum definitions come from `contracts/catalog.md`; do not create alternate verdict names. Percent fields carry percent units; internal weights may be fractions with explicit conversion at boundaries. Null means unavailable/not applicable, never a numeric zero. All timestamps are UTC; human deadlines in this pack are EST.

Use Python type hints, explicit result objects and pure functions for maths. TypeScript strict mode; unknown JSON must be validated, not cast into trust. Pin compatible versions and commit lockfiles when implementation starts. No module reads process environment, wall clock or raw AWS clients deep inside calculations; an injected context supplies dependencies.

## Errors and asynchronous work

HTTP failures use `ApiError`, including validation and unhandled exceptions. Unexpected exceptions are logged with correlation ID, while clients receive no stack traces or secrets. Tool errors become typed tool results. Missing evidence is a normal result, not a service crash. Network retries obey per-run wall-clock limits and source backoff; do not blindly retry malformed inputs or refusals.

State transitions use optimistic concurrency. A terminal result cannot be overwritten by a late worker. Session ID is an unguessable bearer capability in this demo, not a claim of authenticated identity. Never log it in full. Scope idempotency and caches to session. See [API persistence spec](../backend/aplomb/api/SPEC.md).

## Reproducible verification

Use immutable starter CSVs for control tests; never regenerate them during tests. Numeric tests compare unrounded values with the printed-control tolerance. Round only at display. Unit tests use fake clocks/transports/model responses; AWS and live-source checks run separately and record what was actually exercised. A fixture run always carries `flags.fixture = true`.

## Documentation and handoffs

Use repository-root paths in backticks when naming future implementation files; use relative Markdown links only to files that exist. Every owner keeps their spec current when internals materially change. Cross-track contracts change in `contracts/` first with examples and version note. A TODO must name a responsible track, dependency and fallback; a “done” claim needs a test or observed result.

## UI behavior

Keyboard-accessible controls, visible focus, textual status with color, responsive layout and reduced motion support are required. Labels display period and currency near risk figures. Generated prose is rendered from typed segments as text, never injected HTML. Stale preview requests must not replace newer results. Page loading, empty, unavailable, partial and failed states are implemented deliberately.
