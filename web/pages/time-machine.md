# Time Machine — cutoff first, outcome later

**Owner:** T15. **Tier:** P1, cut item 3. Route `/time-machine/?runId=...`. [Historical backend](../../backend/aplomb/timemachine/SPEC.md).

## Before analysis

Load `/replay/presets`; show earliest/latest supported dates, explicit why labels and notices. User selects persona, permitted asOf date and confirmed move. No “before 2022 crash” shortcut unless available history supports it. Display warning: model knowledge is not erased, adjusted/revised data is not original vintage, universe selected later. This is historical simulation, not forecast validation or offline replay.

## Decision view

Create replay run; reuse Decision Desk result/timeline with strong “Information cutoff” banner. Gate panel shows visible/withheld row counts and last available dates per dataset. Unavailable stress/release evidence appears nee, never hidden. No live research, on-demand fetch or current headline panel. Future outcome cards remain absent until explicit reveal.

## Reveal

Only succeeded replay enables “Reveal later outcomes.” Choose until within supported snapshot range and after cutoff. POST reveal gives a separate deterministic ledger; charts start at 100 for each fixed scenario and show realized return/drawdown/actual dates with links to reveal facts. Keep original verdict, signed hash and brief unchanged. Caption: observed hypothetical outcomes in this dataset, not evidence of a prediction or general superiority.

## Verification

TMUI-01 range/unsupported-date controls, TMUI-02 date-gated missingness visible, TMUI-03 separate namespaces for run/reveal references, TMUI-04 no future outcomes before reveal, TMUI-05 original result/hash unchanged, TMUI-06 feature-disabled deep link explains unavailable state, TMUI-07 keyboard chart/table alternative. Loading/reveal error preserves original signed decision and allows retry.
