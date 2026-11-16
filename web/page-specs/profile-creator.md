# Profiles — fictional creator and plan confirmation

**Owner:** T13, services T06/T08. **Tier:** P1, cut item 4. Route `/profiles/`; access from persona menu rather than eighth primary sidebar page.

## Form and text entry

Form: fictional display label, optional age, risk level, horizon min/max, objective, experience, reporting CAD/USD currency, interests/exclusions/ESG/controversy/speculation preferences, fictional capital and optional holdings. Do not request real contact/account information. Validate required fields, positive capital, duplicate tickers/negative weights, 100±0.01 total and <=40 positions.

Text draft starts profile_draft run. The values already entered in the form go with it as confirmed `fields`, and applying the draft fills the form on screen (additive: fields the draft does not propose keep their value, investorContext merges key by key; an edit stays an edit, a new profile records fromDraftRunId). The review lists every proposed field with its value and explanation, and every withheld field with its bilingual question. Display inferred fields with explanations, unresolved questions and provisional values visibly marked; no autosave. Holding tickers outside the loaded snapshot universe block Save, with the supported list under the holdings table. If required data was absent in text, user must confirm it before Save. Null rules/portfolio request code-derived plan/proposed mix, labelled assumptions. Default-profile copy must obtain a new ID; defaults themselves cannot be deleted/replaced.

## Persistence and edits

Save POST `/profiles` after confirmation, optional fromDraftRunId. Replace/delete custom profiles through their endpoints; show stale-version 409 with reload while retaining unsaved form. Rules/holdings on defaults use session overlays, not global edits. Preview financial feasibility separately from evidence cleanliness: no-controversy data means nee, even if numeric rules pass.

## Acceptance

CRE-01 required/unresolved form blocks save. CRE-02 user confirms draft before persistence. CRE-03 invalid weights expose actual sum. CRE-04 session overlays don't affect other sessions. CRE-05 custom update conflict handling. CRE-06 disabled-flag bookmarked route. CRE-07 labels/keyboard/mobile. Form fields do not imply this is a personal advisory onboarding flow.
