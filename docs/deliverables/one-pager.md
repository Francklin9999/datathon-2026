# Aplomb — evidence before conviction

**A hypothetical portfolio change should come with an inspectable explanation.** Aplomb helps a person compare an idea with a fictional investor's plan before interpreting a persuasive narrative. Simulation only. Fictional profiles. Not financial advice.

## The product

Choose Robert, Amira or Mateo, inspect the portfolio and plan assumptions, then test a hypothetical change. Python computes funding, exposures, historical risk and rule outcomes. Agents plan and explain the work. Every approved numeric segment links to a run-local fact with its method, inputs, source, period and currency. Different plans can produce different outcomes for the same investment idea.

On the frozen starter snapshot, Robert's hypothetical +25-point TSLA move conflicts with six counted checks, has one tension and one pass. Historical volatility is 16.96%, maximum drawdown 25.31%, and calendar-2022 stress loss 21.88%. The grid boundary before the first rule conflict is 6.0 points for Robert and 11.0 for Amira; it is not a guarantee that every rule passes. Mateo's Energy exclusion rejects CNQ even when financial checks pass; absent controversy evidence remains explicitly unresolved.

## Why the explanation is inspectable

Models do not supply the risk calculations or override thresholds. A run-local ledger connects results to inputs. Code checks references, numeric grammar and comparisons; interpretation review and the configured output guardrail run before signing. Unsafe sentences are removed or signing fails. The ledger digest detects changes to recorded content; it is not proof that a source or interpretation is correct.

The static Next.js client sits behind CloudFront and private S3. API Gateway and Lambda validate requests. A separate worker uses Bedrock, deterministic Python tools and durable DynamoDB/S3 checkpoints. Conditional writes protect session ownership, idempotency and cancellation; CloudWatch ties outcomes to run IDs. The system has no trading tool.

## Evidence and limits

The [acceptance report](acceptance.md) and [gate report](evidence/report.json) provide reproducible offline results and measured local latency. Earlier [AWS captures](../../infra/evidence/aws-architecture-2026-11-14.json) document genuine Bedrock execution and persisted results on a separately identified release. Browser and current deployed-release acceptance remain blocked; the pack does not claim submission readiness.

Results describe historical samples, assumed plans and dataset vintages. Survivorship, adjustments, FX filling, macro revisions and missing ESG evidence are disclosed. ETF rules do not look through to constituents. World exposure does not establish financial impact. Historical gating cannot remove knowledge embedded in a model. Research, world/replay and sabotage must remain disabled in deployment until their live paths are demonstrated.
