# backend/aplomb/profiles — personas, portfolios, profile creator

**Track:** T06 (with rules). **Tier:** defaults P0; creator P1 (cut item 4, D-02).
**Read first:** `contracts/schemas.md` §4, `contracts/api.md` §3, `docs/02-DECISIONS.md` (D-17, A-10 to A-13).

## 1. Responsibility

- Hold the three default personas exactly as the brief describes them, each with a fictional portfolio and a rule set.
- Store and serve custom profiles created in the UI (form or free-text draft).
- Apply per-session edits (thresholds, positions) on top of defaults without altering the defaults for anyone else.
- Never interpret a profile on its own: turning a profile into thresholds is the optimizer's job (`optimizer/SPEC.md` §3); evaluating rules is the rule engine's job (`rules/SPEC.md`).

## 2. Public interface

```python
# backend/aplomb/profiles/service.py
class ProfileService:
    def list(self, session_id: str) -> list[Profile]: ...
    def get(self, session_id: str, profile_id: str) -> Profile: ...            # raises NotFound
    def create(self, session_id: str, req: ProfileCreate) -> Profile: ...
    def replace(self, session_id: str, profile_id: str, req: ProfileCreate, version: int) -> Profile: ...
    def delete(self, session_id: str, profile_id: str) -> None: ...
    def patch_rule(self, session_id: str, profile_id: str, rule_id: str, threshold: float | None, enabled: bool | None) -> Profile: ...
    def set_portfolio(self, session_id: str, profile_id: str, portfolio: PortfolioInput, version: int) -> Profile: ...
    def rederive_rules(self, session_id: str, profile_id: str, reset: bool, window: WindowSpec) -> tuple[Profile, dict[str, Fact]]: ...
```

Consumes: `datastore.Universe` (ticker validation), `optimizer.derive_thresholds`, `optimizer.propose_portfolio`, the key-value store from `api/SPEC.md` §4.
Provides to: API routers (§3 of `contracts/api.md`), tool `profile.get`, agents (profile summary for prompts).

### Storage

Table `aplomb-profiles` (`api/SPEC.md` §4): defaults are loaded from `backend/aplomb/profiles/defaults.json` at start; a session's edits to a default are stored as an **overlay** item (`pk = SESSION#<sid>`, `sk = OVERLAY#<profileId>`) containing only changed rules and positions. `get` merges default + overlay. Custom profiles are full items (`sk = PROFILE#<profileId>`).

`version` starts at 1 and increases by 1 on every change to the merged profile. Any change invalidates the cached overview and marks the Home brief stale (`api.md` 3.12). Overview and performance responses are cached per process (64 entries, least recently used out), keyed by the snapshot version, the merged profile's full content and the query, so an edit, another session's overlay or a new snapshot never reuses an entry while sessions reading the same unedited default share one.

## 3. The three default personas

Profile text is taken from the brief (English PDF pages 5–7). Portfolios, capital amounts and rule thresholds are **ours** (A-13) and are labelled fictional and assumed in the UI.

### 3.1 Robert

| Field | Value | Source |
|---|---|---|
| `profileId` | `robert` | — |
| Age, occupation | 59, healthcare professional | brief p.7 |
| `riskLevel` | `low_moderate` | brief p.7 "Low to moderate" |
| `horizonYears` | `{ min: 3, max: 5 }` | brief p.7 |
| `objective` | `preserve` — "preserve capital while maintaining some growth potential" | brief p.7 |
| `experience` | `advanced` | brief p.7 |
| Preferences | established companies and business models he understands; values stability and quality; little interest in crypto; follows markets and is interested in new opportunities; may be tempted by a highly publicized company even when riskier than he would normally prefer | brief p.7 |
| `preferences` object | `cryptoInterest: "none"`, `avoidSpeculative: true`, `wantsDiversification: true`, `esgFocus: false`, `avoidControversies: false`, `excludedAssetClasses: ["crypto"]` | our encoding |
| Persona test | The system must challenge a request that conflicts with the profile, explain the risks and avoid simply agreeing | brief p.7 |
| Fictional capital | 600,000 CAD | A-13 |

Portfolio (weights in %; sums to 100):

| Ticker | Weight | Why it is there (assumption) |
|---|---|---|
| XBB.TO | 30 | Core Canadian bonds for capital preservation |
| ZST.TO | 15 | Ultra-short bonds as near-cash for a 3–5 year horizon |
| AGG | 5 | US aggregate bonds |
| XIU.TO | 15 | Broad Canadian equities |
| SPY | 10 | Broad US equities |
| RY.TO | 5 | Established company |
| FTS.TO | 5 | Established utility |
| ENB.TO | 4 | Established company |
| JNJ | 4 | Established company |
| PG | 4 | Established company |
| GLD | 3 | Diversifier |

### 3.2 Mateo

| Field | Value | Source |
|---|---|---|
| `profileId` | `mateo` | — |
| Age, occupation | 41, operations manager | brief p.6 |
| `riskLevel` | `moderate` | brief p.6 |
| `horizonYears` | `{ min: 8, max: 12 }` | brief p.6 |
| `objective` | `balanced` — "balanced capital growth over the medium and long term" | brief p.6 |
| `experience` | `intermediate` | brief p.6 |
| Preferences | high importance on ESG factors; avoid companies involved in significant environmental or social controversies; balance between growth and stability; open to emerging technologies when they fit his risk profile, little interest in highly speculative investments | brief p.6 |
| `preferences` object | `esgFocus: true`, `avoidControversies: true`, `avoidSpeculative: true`, `cryptoInterest: "low"`, `excludedSectors: ["Energy"]`, `wantsDiversification: true` | our encoding (A-11) |
| Persona test | The system must use more than return and risk: financial factors and personal preferences | brief p.6 |
| Fictional capital | 250,000 CAD | A-13 |

| Ticker | Weight | Why it is there (assumption) |
|---|---|---|
| ESGV | 28 | ESG-screened broad US equity fund (the only screened fund in the starter pack) |
| XBB.TO | 25 | Canadian bonds for stability |
| AGG | 7 | US aggregate bonds |
| ZST.TO | 5 | Near-cash |
| MSFT | 5 | Technology exposure sized for a moderate profile |
| CNR.TO | 5 | Established company |
| RY.TO | 5 | Established company |
| FTS.TO | 4 | Utility |
| ATD.TO | 4 | Consumer staples |
| JNJ | 4 | Health care |
| PG | 4 | Consumer staples |
| GLD | 4 | Diversifier |

No controversy screening was done on these names: no data exists for it (`LIM_NO_CONTROVERSY_DATA`). The portfolio contains no Energy-sector holding so that his exclusion rule passes at baseline.

### 3.3 Amira

| Field | Value | Source |
|---|---|---|
| `profileId` | `amira` | — |
| Age, occupation | 26, software engineer | brief p.5 |
| `riskLevel` | `high` | brief p.5 |
| `horizonYears` | `{ min: 15, max: null }` | brief p.5 "15 years or more" |
| `objective` | `growth` — "grow her capital over the long term" | brief p.5 |
| `experience` | `intermediate` | brief p.5 |
| Preferences | very interested in AI and emerging technologies; open to high-growth companies and significant volatility; interested in crypto assets; still wants some diversification and does not want to invest exclusively in technology | brief p.5 |
| `preferences` object | `themesOfInterest: ["ai", "semiconductors", "software", "crypto"]`, `cryptoInterest: "open"`, `wantsDiversification: true`, `avoidSpeculative: false`, `esgFocus: false` | our encoding |
| Persona test | An aggressive profile without reading "high risk" as "anything goes", while respecting her wish for diversification | brief p.5 |
| Fictional capital | 60,000 CAD | A-13 |

| Ticker | Weight | Why it is there (assumption) |
|---|---|---|
| NVDA | 8 | AI / semiconductors interest |
| MSFT | 8 | Technology |
| GOOGL | 6 | Technology |
| SHOP.TO | 5 | High-growth Canadian company |
| AMZN | 5 | Growth |
| QQQ | 12 | Growth-heavy US fund |
| SPY | 12 | Broad US equities |
| XIU.TO | 10 | Broad Canadian equities |
| BTC-USD | 6 | Crypto interest |
| ETH-USD | 3 | Crypto interest |
| JPM | 4 | Outside technology |
| CNR.TO | 4 | Outside technology |
| ATD.TO | 4 | Outside technology |
| JNJ | 3 | Outside technology |
| XBB.TO | 5 | Diversifier |
| GLD | 5 | Diversifier |

### 3.4 Default rule sets

Thresholds are the derived values in `contracts/controls.md` §7. Display order defines the `R` codes.

| Code | Robert | Mateo | Amira |
|---|---|---|---|
| R1 | `cap.position` 10% | `cap.position` 15% | `cap.position` 25% |
| R2 | `cap.sector` 20% | `cap.sector` 30% | `cap.sector` 40% |
| R3 | `cap.growth_assets` 55% | `cap.growth_assets` 80% | `cap.asset_class.crypto` 15% |
| R4 | `floor.fixed_income` 35% | `floor.fixed_income` 10% | `floor.diversifiers` 8% |
| R5 | `limit.volatility` 9% | `limit.volatility` 12% | `limit.volatility` 22% |
| R6 | `limit.stress_2022` 9% | `limit.stress_2022` 15% | `limit.stress_2022` 33% |
| R7 | `limit.drawdown` 18% | `limit.drawdown` 24% | `limit.drawdown` 44% |
| R8 | `exclude.asset_class.crypto` | `cap.asset_class.crypto` 5% | `flag.attention` |
| R9 | `flag.attention` | `exclude.sector.energy` | `flag.rate_cycle` |
| R10 | `flag.rate_cycle` | `evidence.controversy` | `sim.only` |
| R11 | `sim.only` | `flag.attention` | — |
| R12 | — | `flag.rate_cycle` | — |
| R13 | — | `sim.only` | — |

`[CONTROL]` Each default portfolio passes all financial rules at baseline (`contracts/controls.md` §8). Robert and Amira are **compatible**. Mateo is **insufficient** with starter data: the controversy rule is `nee`, not proof that his holdings are controversy-free. A unit test asserts these outcomes.

Plain-language labels (English; French in `defaults.json`):

| RuleId | Label template |
|---|---|
| `cap.position` | No single stock or crypto asset above {threshold}% of the portfolio |
| `cap.sector` | No sector above {threshold}% of the portfolio (directly held stocks) |
| `cap.growth_assets` | Stocks, equity funds and crypto together at most {threshold}% |
| `floor.fixed_income` | Keep bonds and cash at {threshold}% or more |
| `floor.diversifiers` | Keep bonds, cash and gold together at {threshold}% or more |
| `cap.asset_class.crypto` | Crypto assets at most {threshold}% |
| `limit.volatility` | Portfolio volatility at most {threshold}% a year |
| `limit.stress_2022` | A repeat of 2022 may cost at most {threshold}% of the portfolio |
| `limit.drawdown` | Largest historical peak-to-trough fall at most {threshold}% |
| `exclude.asset_class.crypto` | No crypto assets |
| `exclude.sector.energy` | No directly held Energy-sector companies |
| `evidence.controversy` | No company involved in a significant environmental or social controversy (needs outside evidence) |
| `flag.attention` | Show when the requested asset is drawing unusual public attention |
| `flag.rate_cycle` | Show how the portfolio behaved while interest rates rose |
| `sim.only` | Simulation only: no order is ever placed |

Edit bounds (`PolicyRule.bounds`): caps on positions and sectors 2–50 step 1; `cap.growth_assets` 0–100 step 5; floors 0–100 step 1; `limit.volatility` 2–40 step 0.5; `limit.stress_2022` 1–60 step 0.5; `limit.drawdown` 2–80 step 1.

## 4. Profile creator (P1)

Two entry paths, same result (a `Profile` saved under the session):

### 4.1 Form path

`POST /v1/profiles` with core fields. When `rules` is null the service calls `optimizer.derive_thresholds(risk_level, horizon, preferences)`; when `portfolio` is null it calls `optimizer.propose_portfolio(...)` (`optimizer/SPEC.md` §5), which returns a starting mix labelled "proposed starting portfolio, hypothetical".

Mapping from preferences to rules (applied by `derive_thresholds`):

| Preference | Rule added |
|---|---|
| `cryptoInterest = "none"` or `"crypto"` in `excludedAssetClasses` | `exclude.asset_class.crypto` |
| `cryptoInterest = "low"` or `avoidSpeculative` | `cap.asset_class.crypto` at half the formula value |
| `cryptoInterest = "open"` | `cap.asset_class.crypto` at the formula value |
| each entry of `excludedSectors` | `exclude.sector.<slug>` |
| `avoidControversies` | `evidence.controversy` |
| `wantsDiversification` and growth cap = 100% | `floor.diversifiers` 8% (A-10) |
| growth cap < 100% | `cap.growth_assets` and `floor.fixed_income` |
| always | `cap.position`, `cap.sector`, `limit.volatility`, `limit.stress_2022`, `limit.drawdown`, `flag.attention`, `flag.rate_cycle`, `sim.only` |

### 4.2 Free-text path

1. Web calls `POST /v1/runs` with `kind: "profile_draft"` and the text.
2. The Planner (fast model) extracts fields into a `Profile` skeleton. It may only fill fields that the text supports; everything else stays unset and appears in `unresolved` with a question. It must not invent an age, an amount or a holding.
3. Code derives rules and, if no holdings were given, a proposed portfolio.
4. The result (`ProfileDraftResult`) is shown in the creator form, pre-filled, with an explanation per inferred field. Nothing is saved until the user presses Save (`POST /v1/profiles` with `fromDraftRunId`).

Validation applied to every created or edited profile:

| Check | Error |
|---|---|
| Name 1–40 characters | `validation_error` |
| Weights ≥ 0 and sum to 100 ± 0.01 | `validation_error` with the actual sum |
| Each ticker exists in the universe (or was fetched on demand) | `not_found` listing unknown tickers |
| At most 40 positions | `validation_error` |
| `totalValue` > 0 | `validation_error` |
| Reporting currency CAD or USD | `validation_error` |
| Real personal data is not requested: the form has no field for real names, account numbers or contact details | by design (brief p.14 privacy) |

## 5. Tests

| ID | Test |
|---|---|
| PRF-01 | Defaults load; each has the fields of §3; weights sum to 100 |
| PRF-02 | Default financial checks pass; Robert/Amira compatible, Mateo insufficient without controversy evidence `[CONTROL]` |
| PRF-03 | Patching Robert's `cap.position` in session A does not change it in session B |
| PRF-04 | `rederive_rules(reset=True)` restores the values of `contracts/controls.md` §7 |
| PRF-05 | Creating a profile with weights summing to 99 fails with the sum in the message |
| PRF-06 | Replacing with a stale `version` returns `conflict` |
| PRF-07 | Default profiles cannot be deleted or replaced |
| PRF-08 | A draft from text that states no age leaves `age` null and lists it in `unresolved` |

## 6. Definition of done

- `defaults.json` matches §3 and validates against the Pydantic `Profile` model.
- All eight tests pass without network access.
- `GET /v1/profiles` returns the three defaults in the order Robert, Amira, Mateo (the demo starts with Robert).
- French labels exist for every rule label and blurb (or repeat English if the bilingual feature is cut).

## 7. Implementation status (T06, 2026-11-14)

`defaults.py` builds the three personas (thresholds and printed derivation inputs from controls §5/§7) and writes `defaults.json` (`uv run python -m aplomb.profiles.defaults`); a test fails on drift. `rulebuilder.make_rule` builds validated `PolicyRule`s for defaults and derivation. `service.ProfileServiceImpl(repository, snapshot, clock, deriver, proposer)` implements T03's `ProfileService`: defaults + session overlays (only changed rules/portfolio stored; version = 1 + overlay revision), custom profiles (`p_` + 10 Crockford base32 characters as in the contract pattern), rule PATCH with bounds and `editable` checks, portfolio validation (sum 100 ± 0.01, at most 40 positions, unique known tickers, positive value), optimistic versions, deterministic `overview` (snapshot, YTD/1y/3y/5y returns or null, risk with `riskCategory`, top five positions, correlation of assets with defined correlations, rule checks, facts) and `performance` (constant-weight index from total value, optional benchmark).

`deriver`/`proposer` come from the optimizer (T07); without them rule derivation, custom profiles without rules and portfolio proposals return `upstream_unavailable`. `frontier` returns `feature_disabled` and `brief` belongs to the run coordinator (T08). PRF-04 (rederive) is tested with T07; PRF-08 (free-text draft) belongs to T08.
