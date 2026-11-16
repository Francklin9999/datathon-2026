# Investor Lab service

The [Investor Lab page](../../../web/page-specs/investor-lab.md) uses a deterministic state machine:

`initial → research → contrast → initial | review → saved`

There are three historical checkpoints for new/full sessions and one targeted checkpoint for quick sessions. The stored record pins the price sample, candidate profile and original profile revision. Public responses reveal only the current historical prefix and already completed observations.

## Data boundary

Lab records live in the existing profiles table under `INVESTOR_LAB#{sessionId}`. They are excluded from the profile list and are available only through the session capability. Mutations check the Lab revision, expected stage and action semantics.

Dates, proxy identities and original source URLs are withheld until review. Evidence captures must have a publication date no later than the checkpoint. The source manifest records provenance for statements used in cards. Unverified historical 13F captures do not enter the masked exercise.

## Profile boundary

Initial, research and contrast mutations cannot write a profile. Confirmation applies only accepted settings, validates numeric bounds, records the user's explanation and saves a dated review in `investorContext.playbook`. A new session requires explicit confirmation of all required settings. A default profile is copied into a session-owned custom profile.

For existing custom profiles, unrelated portfolio, accounts, preferences and policy data are retained. Both the original profile revision and Lab revision are checked. Profile and Lab changes use one storage transaction; failure leaves both unchanged. A repeated confirmation of a saved session is idempotent.

Direct playbook edits also require the current profile revision and a reason. They append a history record and do not modify investment limits.

## Contracts

Typed models are defined in [investor_lab.py](../contracts/investor_lab.py), exported through the shared contract registry and validated by the web client. Endpoint descriptions are in [contracts/api.md](../../../contracts/api.md#investor-lab-and-investment-playbook).
