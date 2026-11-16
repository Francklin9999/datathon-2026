# Aplomb — evidence before conviction

**A self-explaining agentic assistant that tests an investment idea against a fictional investor's own plan, and shows what supports every conclusion.** Simulation only · fictional profiles · not financial advice. Live: https://d1r325uzu5fe7x.cloudfront.net

## Problem
A tempting idea ("put 25% in Tesla") is usually judged on its story, not on the person. Generic assistants agree, or quote numbers nobody can check. The useful question is personal: *does this move fit this investor's plan, and if not, how much would?* The three case personas pose it differently. Robert (59, 3–5 years, preserve capital) is tempted by a publicized stock; Amira (26, high risk) wants growth without giving up diversification; Mateo (41, balanced) excludes controversial sectors.

## Agentic approach
Six roles, each with one job. The **planner** frames the request, picks research questions and up to four optional analyses (correlation with current holdings, the asset's own metrics, a calendar year, an extra stress window) that code then runs; anything it cannot run is reported as skipped. The **researcher** reads allow-listed official sources (Bank of Canada, Federal Reserve, Statistics Canada); the **quant** calls deterministic Python tools (adjusted returns, volatility, drawdown, 2022 stress, concentration, FX); the **risk officer** checks every rule of the profile; the **writer** drafts in English or French from ledger facts only; the **auditor** verifies every number and comparison in code, adds a model review and Bedrock Guardrails, strikes unsupported sentences, then signs. Models never compute risk or move a threshold.

## Originality
- **"How much would fit?"** instead of yes/no: the largest size compatible with the plan.
- **A run-local fact ledger**: every figure links to its method, inputs, source rows, period and currency; a signed hash makes later edits detectable.
- **Governance that is tested**: an audit test slips a false sentence into a real brief, and the real audit must catch it.
- **Time Machine**: replay a decision as of a past date with only the data available then, then reveal what followed.
- **Strategies**: simulate rebalancing, contribution or risk-guard rules on five years of history against doing nothing.

## Data sources
Starter dataset: 31 assets (20 Canadian and U.S. equities, 9 ETFs including bonds, gold and ESG, Bitcoin, Ether), adjusted daily prices from 2021-11-12 to 2026-11-12, dividends and splits, Bank of Canada USD/CAD, Bank of Canada and FRED macro series. Added: Bank of Canada global FX (9 reporting currencies), Wikipedia page views (attention flag), dated official events and major earthquakes, hazards and emissions facilities. One pinned, hashed snapshot; every dataset has a passport giving source, licence, coverage, availability rule, processing and limitations.

## Explainability
Click any figure to open its fact. The run trace shows each step, tool call, dataset rows read, model, tokens and timing, including which plan analyses ran or were skipped. The audit report lists checks, struck sentences, the guardrail result and the ledger hash. Facts, assumptions and fiction are labeled; missing evidence is reported as *not enough evidence*, never guessed; event links say *impact not established*.

## Concrete user benefits
A signed, sourced decision brief in under a minute (42 to 56 s in live AWS runs). For TSLA +25 points, Robert hits six rule conflicts and a 6-point limit; Amira hits three, with an 11-point limit. At +10 the same idea is a tension for Amira but still a conflict for Robert. Mateo's Energy exclusion blocks CNQ even though eight other checks pass. A what-if slider and the Time Machine test sensitivity. English and French; there is no trading tool.

**On AWS**: CloudFront and private S3 for the site; API Gateway and Lambda for the API; a Lambda worker runs the agents on Amazon Bedrock with Guardrails; DynamoDB keeps profiles and runs, S3 keeps snapshots and evidence, CloudWatch ties outcomes to run IDs.

**Validated**: 1,278 Python, 411 web and 7 infrastructure tests, including scripted agent runs and audit failure cases; every release records live checks, artifact hashes and a rollback in `infra/evidence/`.
