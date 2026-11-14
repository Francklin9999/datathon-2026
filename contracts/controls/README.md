# Numeric reference scripts

These standard-library scripts were recovered from Claude's interrupted specification session and rerun against the unchanged organizer CSVs. They are independent reference calculations, not the product backend. Run from repository root with the data directory argument shown in [controls](../controls.md).

| Script | Prints |
|---|---|
| [controls.py](controls.py) | Source counts/calendar/FX, asset risk/2022 returns, portfolio controls and reference mixes |
| [rules_ctl.py](rules_ctl.py) | Derived thresholds, rule checks, funding examples and 0.5-point first-conflict boundaries |
| [rate_ctl.py](rate_ctl.py) | Rate-cycle, YTD and trailing-year portfolio returns |

Reference scripts retain Claude's direct, small-dataset approach, including loading shared helper code for comparison. They are intentionally not the production architecture. `scripts/check_specs.py` independently asserts key controls and fixture integrity; product tests must cover the full module acceptance cases.

Completion corrections: the rules reference now includes Mateo's missing controversy evidence at baseline, and named-holding funding rejects insufficient listed donors rather than spilling silently into other holdings. Ordered donor depletion matches the published from-holdings control examples. The product optimizer separately returns a structured no-feasible-mix result; the reference script is restricted to the three default risk budgets with valid reference mixes.

Numeric conventions: internal fractions, CAD returns on master calendar, sample standard deviation × sqrt(252), negative drawdown printed here versus positive magnitude on API, constant-weight compounding, no price/FX look-ahead. The size grid permits tension/nee and stops at first conflict; the phrase “max compatible” in historical script output names that boundary only.
