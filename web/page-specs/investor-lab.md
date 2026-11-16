# Investor Lab

Route: `/investor-lab/`. Entry points: profile creation, “Test my profile” in the profile menu, and the portfolio playbook. The route uses the existing `profile_creator` feature flag.

## Experience

- **New profile:** collect the investor's goal, horizon, cash needs, financial capacity, willingness to accept risk, experience and research interest. Holdings are optional and remain fictional.
- **Quick check:** confirm circumstances and complete one targeted checkpoint.
- **Full Investor Lab:** complete three contrasting checkpoints with a hypothetical proxy version of the selected portfolio.
- **At each checkpoint:** record an initial action and target company weight; consult masked evidence and record why; submit a final action, explanation and revisit condition; then answer a contrasting scenario.
- **Review:** show stated circumstances, observed choices and proposed settings separately. Each proposal has its basis, current value and suggested value. The fictional starting portfolio is also shown for confirmation. Required settings for a new profile must be confirmed. Existing settings change only when selected.
- **After confirmation:** select the saved profile, show its editable investment playbook and dated review history, and offer a first investigation based on the selected interest.

The exercise does not grade returns or silently infer a risk label from a single choice. “Hold” retains the current weight; “buy” and “sell” must increase and decrease it respectively. A rebalance allows either direction.

## Evidence and limitations

The historical proxy exercise progressively exposes the pinned price prefix. Calendar dates and recognizable company identities remain hidden until review. Research cards expose only evidence available at the checkpoint; source links become visible at review so they do not reveal future company pages during the exercise.

Company statements have dated source captures. Disclosures without verified historical publication availability are withheld from the exercise. Optional institutional comparisons after the Lab retain dates and coverage caveats and do not assign a personality label.

The proxy basket uses retrospectively adjusted USD prices. It does not reproduce the selected portfolio's actual historical performance, taxes, transaction costs or full investment opportunity set. These limitations are visible before choices are made.

## Persistence and failures

The server owns Lab progress and records every change with an expected revision. `?lab=` resumes the same session after refresh. A stale revision or profile version requires reloading; it does not overwrite later edits. Confirmation atomically saves the profile and marks the Lab as saved. Repeating a successful confirmation returns the saved profile.

The page provides an initial loading state, an empty recent-sessions state, a feature-unavailable state, recoverable request errors, source coverage limitations and a saved state. A failed save keeps the review available for retry.

## Verification

Backend tests cover availability gates, action constraints, session isolation, revision conflicts, explicit acceptance, transaction rollback and preservation of existing profile data. Browser checks cover creation, research, contrasting answers, confirmation, restoration, profile integration and responsive layouts at 390 and 1440 pixels.
