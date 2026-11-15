# Profile and policy implementation notes

Typed conditional trees have bounded size and depth, three-valued evaluation and fact dependencies; they use the same portfolio measurements and verdict engine as standard rules. Explicit permitted classes materialize exclusion rules, with conflicting attempts to disable those rules rejected. Country and quotation currency remain proxies. ESG evidence absence produces an insufficient-evidence result, not an inferred score.

Account editing is version-checked and session-scoped. Quantities are accepted only with their dated provenance; changed/removed quantities are retained in history and invalidated for transferred positions rather than inferred from weights. Seed input values are marked as defaults and copied/user-edited fields retain input-origin metadata.

Custom themes use explicitly dated user/imported exact-ticker true/false classifications. Every held ticker must be classified and the definition must be visible as of the query date; incomplete or future definitions yield an unknown result. Classification provenance is recorded in the fact ledger. No fund look-through is inferred. Country-specific regulatory policy and external controversy evidence require verified sources and are not inferred.

Native account value and currency receipts retain `nativeValueOrigin` and `nativeValueSource`; new account input defaults to user, imported/assumption are explicit, and legacy unknown provenance remains unknown after refresh. Private appraisal receipts preserve their supplied origin and description independently of FX verification.
