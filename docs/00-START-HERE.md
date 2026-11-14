# 00 — Team entry point

## First fifteen minutes

1. Read [product scope](01-PRODUCT.md) and [decisions](02-DECISIONS.md). `[D]` means the owner decided; `[A]` means an unconfirmed usable default; `[O]` needs an owner to resolve it.
2. Read [track boundaries](04-TRACKS.md), claim one track in the team coordination channel, and announce the files you will touch. The owner column names responsibility, not a person who has already volunteered.
3. Read [contract conventions](../contracts/README.md), your relevant [API endpoints](../contracts/api.md), [schemas](../contracts/schemas.md) and your module/page spec.
4. Build against [fixtures](../contracts/fixtures/README.md) and narrow interfaces immediately. Do not wait for AWS or a neighboring track's implementation.
5. Agree with your consumer on one contract example, then implement and test it. Raise contradictions to T01 before changing a shared shape.

## Source-of-truth order

Organizer challenge requirements constrain the product. Explicit owner decisions in `02-DECISIONS.md` settle scope. `contracts/` owns cross-track interfaces. Module specs own internals and their tests. Fixtures illustrate those contracts; they do not override them. The existing HTML is a design reference, not the application implementation.

## Integration milestones

| Gate | Required evidence | Responsible |
|---|---|---|
| Contract freeze | Shared types, error envelope, fixture validation, assigned tracks | T01 |
| Deterministic slice | Robert +25 TSLA, `/check`, metric citations and slider work locally | T03/T05/T06/T07/T14 |
| Real agent slice | One Bedrock decision completes with persisted genuine steps and audited brief | T02/T08/T10 |
| Product integration | Three profiles, compare, Sources, evidence drilldown, honest error paths | All P0 owners |
| P1 integration | Goal candidates, globe, sabotage, historical gate, creator behind flags | P1 owners |
| Submission | Clean-clone instructions, passing acceptance, real AWS capture and deliverables | T16 |

All tracks can begin together. Integration gates order validation, not permission to start. At Sunday 18:00 EST apply D-02's exact cut order. A hidden feature must also be disabled server-side. Record actual availability in `/meta`.

## Handoff checklist

Provide touched paths, public callable signatures, one valid payload, tests run and their result, remaining limitations, and configuration required. Keep network tests separate from deterministic tests. A stub must return an honest unavailable response; a fixture must have an unmistakable development label.

Read [acceptance](07-ACCEPTANCE.md), [delivery](08-DELIVERABLES.md) and [verification strategy](../tests/SPEC.md) before claiming a track complete.
