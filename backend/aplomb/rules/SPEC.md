# backend/aplomb/rules — the rule engine (Risk Officer)

**Track:** T06. **Tier:** P0.
**Read first:** `contracts/schemas.md` §4.1 and §7, `contracts/catalog.md` §3–4, `contracts/controls.md` §9.

## 1. Responsibility

Given a portfolio (before or after a move), a profile's rules and the facts computed by the quant engine, return one `RuleCheck` per rule and a `Verdict`. Pure code, no model, no I/O. This is the "second line" in the workflow: the component that analyses never validates its own proposal (SRS §4; brief p.9 governance).

The engine does **not** compute market figures. It asks the quant engine for values through a narrow interface and compares them with thresholds.

## 2. Public interface

```python
# backend/aplomb/rules/engine.py
@dataclass(frozen=True)
class RuleInputs:
    snapshot: PortfolioSnapshot            # weights by position, group, sector (from quant)
    metrics: PortfolioMetrics              # volatility, max drawdown, stress replays (from quant), each with its fact id
    evidence: list[Evidence]               # research evidence attached to the run (may be empty)
    attention: AttentionSignal | None
    moved_tickers: list[str]               # assets added or increased by the scenario; empty for a baseline check
    universe: Universe

def check_rules(rules: list[PolicyRule], inputs: RuleInputs, ledger: Ledger, lang_templates: Templates) -> list[RuleCheck]: ...
def verdict_of(checks: list[RuleCheck]) -> tuple[Verdict, VerdictCounts]: ...
def explain_difference(a: list[RuleCheck], b: list[RuleCheck]) -> list[RuleDifference]: ...   # for the compare view (EF-10)
```

`check_rules` registers one `rule_check` fact per rule in the ledger (value, threshold, status) and one `assumption` fact per threshold (`threshold.rule`), so that the brief can cite both.

Consumers: `api` (`POST /check`), `agents` (step `risk_check`), `optimizer` (largest compatible size, scenario ranking), `timemachine`.

## 3. Evaluation (`M_RULE_COMPARE`)

Let `v` be the measured value and `L` the threshold. `TENSION_BAND = 0.10` (A-09). Comparisons use a tolerance of `1e-9`.

| Rule type | Conflict when | Tension when | Otherwise |
|---|---|---|---|
| `cap`, `limit` (comparator `<=`) | `v > L` | `v > (1 − band) × L` | pass |
| `floor` (comparator `>=`) | `v < L` | `v < (1 + band) × L` | pass |
| `exclude` (comparator `== 0`) | `v > 0` | — | pass |
| `evidence` | never directly | verified tier-1 or tier-2 evidence attached to a moved asset | `nee` when no verified evidence; `pass` is **never** returned for an evidence rule (absence of evidence is not evidence of absence) |
| `flag` | — | — | `info` |
| `sim` | — | — | `info` |

A value exactly at a cap is **not** a conflict; it is a tension (example: Amira, 25.0% against a 25% cap, `contracts/controls.md` §9.2).

Any rule that needs a metric the quant engine could not compute returns `nee` with the reason given by quant (`short_history`, `not_visible_at_asof`, `dataset_missing`, `asset_unknown`).

`headroom`: `L − v` for caps and limits, `v − L` for floors, null otherwise.

### 3.1 What each rule measures

| RuleId | Value `v` | `worst` |
|---|---|---|
| `cap.position` | Largest weight among positions with `isSingleName = true` in the snapshot | that asset |
| `cap.sector` | Largest summed weight per `gicsSector` among positions with `assetClass = "equity"` | that sector |
| `cap.asset_class.crypto` | Weight of asset group `crypto` | — |
| `cap.growth_assets` | Weight of groups `equity` + `crypto` | — |
| `cap.theme.<tag>` | Summed weight of positions carrying the tag | — |
| `floor.fixed_income` | Weight of groups `fixed_income` + `cash` | — |
| `floor.diversifiers` | Weight of groups `fixed_income` + `cash` + `commodity` | — |
| `limit.volatility` | `vol.annualized` of the snapshot portfolio over the request window, in % | — |
| `limit.stress_2022` | `max(0, −stress.replay_2022)` in % | — |
| `limit.drawdown` | `drawdown.max` as a positive % | — |
| `exclude.sector.<slug>` | Summed weight of direct equities in that sector | largest offender |
| `exclude.asset_class.<class>` | Weight of that class | largest offender |
| `exclude.ticker.<t>` | Weight of that asset | that asset |
| `evidence.controversy` | — (see §4) | — |
| `flag.attention` | `attention.pageviews_ratio` of the requested asset, if available | that asset |
| `flag.rate_cycle` | `stress.rate_cycle` | — |

Funds are single diversified positions for `cap.position` and `cap.sector` (`LIM_ETF_NO_LOOKTHROUGH` is attached to both checks whenever the portfolio holds a fund). When `etf_holdings` is loaded (P1), a second informational line reports the look-through value; it does not change the status.

### 3.2 Verdict

```text
conflict      if any counted check is "conflict"
tension       else if any counted check is "tension"
insufficient  else if any counted check is "nee"
compatible    otherwise
```

"Counted" = `rule.countsInVerdict` and `rule.enabled`. Disabled rules produce no check.

When the verdict is `insufficient` the headline reads "Inside every rule that could be checked" and lists the rules without evidence; the system never calls this a fit (as in the prototype).

## 4. The controversy rule (Mateo)

- Scope: the assets in `moved_tickers` that are single names. For a baseline check: all single-name holdings.
- Inputs: evidence items whose `subject` is one of those assets and whose `claim` concerns an environmental or social controversy, produced by the Researcher (`research/SPEC.md` §5).
- Status:
  - no such evidence, or only evidence with `verification.status != "verified"`, or only tier 3 → `nee` (`no_evidence_loaded` or `evidence_unverified`). Detail sentence: "No verified controversy evidence was found in the sources searched. This is not a clean bill."
  - at least one verified tier-1 or tier-2 item → `tension`, with `evidenceIds` filled. The engine never escalates to `conflict` on its own: whether a controversy is "significant" is the investor's judgment, and the brief says so.
- With starter data only, this rule is always `nee` (the starter README states the data says nothing about controversies).

## 5. Detail sentences

Built by code from templates, never by a model. One template per `(ruleId family, status)` in English and French, stored in `backend/aplomb/rules/templates.py`. Placeholders are filled with the same formatted strings as the facts' `display`.

| Family | Status | English template |
|---|---|---|
| cap.position | conflict | Largest single position would be {worst} at {value}, above the {threshold} cap. |
| cap.position | tension | Largest single position would be {worst} at {value}, close to the {threshold} cap. |
| cap.position | pass | Largest single position is {worst} at {value}, inside the {threshold} cap. |
| cap.sector | conflict | {worst} would reach {value} of the portfolio, above the {threshold} sector cap. |
| floor.* | conflict | {what} would fall to {value}, below the {threshold} floor. |
| limit.volatility | conflict | Portfolio volatility would be {value} a year, above the {threshold} budget. |
| limit.stress_2022 | conflict | With these weights, calendar 2022 would have cost {value}, above the {threshold} limit. |
| limit.drawdown | conflict | The largest fall in the window would have been {value}, above the {threshold} ceiling. |
| exclude.* | conflict | {worst} belongs to an excluded category ({what}); any size conflicts with this rule. |
| evidence.* | nee | No verified evidence is loaded for {worst}; this rule is not checked. |
| any | nee (short_history) | {worst} has too little price history for this figure. |

(The remaining pass/tension variants follow the same pattern.)

## 6. Differences between two profiles (compare view)

`explain_difference(a, b)` aligns checks by `ruleId` and returns, per rule: both statuses, both thresholds, both values, and a `reason` code: `threshold_differs`, `portfolio_differs`, `rule_only_in_a`, `rule_only_in_b`, `same`. The web compare view renders "Why the answers differ" from this list (EF-10). No model is involved.

## 7. Tests

All expected values are in `contracts/controls.md` §8–9.

| ID | Test |
|---|---|
| RUL-01 | Baselines: Robert/Amira `compatible`; Mateo `insufficient` with controversy `nee`; all have 0 financial conflict/tension |
| RUL-02 | Robert +25 TSLA pro-rata → the eight statuses of §9.1; verdict `conflict`; counts 6 / 1 / 1 |
| RUL-03 | Amira +25 TSLA pro-rata → statuses of §9.2; `cap.position` is `tension` at exactly 25.0 |
| RUL-04 | Mateo +10 CNQ.TO → all financial rules pass, `exclude.sector.energy` conflict, `evidence.controversy` nee |
| RUL-05 | Robert +2 TSLA → `compatible` |
| RUL-06 | Robert +5 BTC-USD → conflict on `exclude.asset_class.crypto` |
| RUL-07 | Disabling a rule removes its check and can change the verdict |
| RUL-08 | Raising Robert's `limit.stress_2022` to 25 changes that rule to pass for +25 TSLA while others still conflict |
| RUL-09 | A metric returned as unavailable (`short_history`) → `nee` for the rules that need it, others unaffected |
| RUL-10 | Verified tier-2 controversy evidence on the moved asset → `evidence.controversy` = `tension`; tier-3 only → `nee` |
| RUL-11 | `explain_difference` Robert vs Amira on the same move lists `threshold_differs` for R1 |
| RUL-12 | Every `(family, status)` pair that can occur has an English and a French template |

## 8. Definition of done

- `check_rules` and `verdict_of` are pure functions with no imports from `agents`, `api` or AWS SDKs.
- RUL-01 to RUL-12 pass.
- `POST /v1/check` for Robert +25 TSLA returns in under 1.5 s locally with a warm data cache.

## 9. Implementation status (T06, 2026-11-14)

`backend/aplomb/rules/`: `definitions.py` (one `RuleDef` per family: type, measured metric, target, unit, bounds, EN/FR label), `templates.py` (EN/FR detail sentences per family/status), `engine.py` (`RuleEngine(ledger, ctx).check_rules(rules, RuleInputs(view, profile_id, moved_tickers, evidence, attention))`, `verdict_of(checks)`, `explain_difference(a, b)`, `compare(type, value, threshold)`).

Values come from quant (`PortfolioView.measure`), so every value fact is a quant fact; the engine registers one `threshold.rule` assumption per thresholded rule (method = the rule's derivation method, `M_USER_INPUT` after an edit, else `M_PROFILE_ASSUMPTION`), the positive 2022 loss fact (`max(0, -stress)`, input = the signed stress fact) and one `rule_check` fact per rule (`count.rules`, variant `<variant>:status:<status>`, inputs = value and threshold facts), following the canonical fixture. Comparison mirrors `contracts/controls/rules_ctl.py` (1e-9 tolerance, 10% band). The evidence rule receives controversy evidence already selected by the researcher; it never returns `pass`. `uv run pytest backend/tests/unit/rules` covers RUL-01…RUL-12 with the controls §8–§9 values.
