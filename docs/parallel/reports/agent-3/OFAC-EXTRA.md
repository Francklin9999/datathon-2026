# OFAC anonymous access and reuse check

Checked 2026-11-15. Assigned source rows: `SRC-136` and `MASTER-055`.
Disposition: **reuse rights not established; no runtime capture**.

OFAC's [Sanctions List Service](https://ofac.treasury.gov/sanctions-list-service)
and [Recent Actions](https://ofac.treasury.gov/recent-actions) pages returned
anonymous HTTP 200 without credentials, login, or payment. The service describes
its lists as “Sanctions list data ready for immediate download.” This establishes
intended download access but does not itself establish a redistribution licence.
The recent-actions page yielded ten official dated publication links, spanning
2026-10-21 through 2026-11-13, out of 3,187 results. This is an evidence sample
only and is neither a complete list nor sanctions screening.

The OFAC footer links directly to Treasury's
[Site Policies and Notices](https://home.treasury.gov/subfooter/site-policies-and-notices)
and [Privacy Policy / Legal Disclaimers](https://home.treasury.gov/subfooter/privacy-policy).
Both returned HTTP 200. Neither captured page provides an affirmative dataset
reuse licence. The legal notice says the government “does not represent that its
use would not infringe privately owned rights” and says Treasury does not endorse
commercial products. Download access and the `.gov` hostname are therefore not
recorded as a blanket redistribution grant.

The linked sanctions application
`https://sanctionslist.ofac.treas.gov/Home/SdnList` returned HTTP 200 with a
JavaScript-only application shell. Its own anonymous static fallback,
`https://sanctionslist.ofac.treas.gov/static/`, returned HTTP 403. No access
restriction was bypassed. A check for authoritative federal public-domain law
text returned HTTP 403 from `copyright.gov/title17/92chap1.html` and HTTP 404
from the queried `uscode.house.gov` section link; these failures do not establish
that the law is unavailable elsewhere or that reuse is prohibited.

The exact remaining blocker is an applicable affirmative OFAC/Treasury reuse
statement or authoritative rights evidence establishing permission for the chosen
government-authored dataset. The sanctions file endpoint and schema would also
need verification before a sanctions list capture. A Recent Actions publication
metadata provider is feasible once its reuse basis is established. It would use
official `/recent-actions/YYYYMMDD` identifiers, retain date precision and
capture-time availability, and contain no coordinates, geographic assignments,
issuer links, or identity matches inferred from names.

Evidence is in `docs/evidence/parallel/agent-3/ofac-extra/`: `access.json` records
access outcomes and SHA-256 hashes of the six retrieved HTML pages; `.txt` files
make those same pages readable; `recent-action-metadata.evidence.json` records
the ten exact publication links and source text. These files are evidence only.
No provider module, runtime bundle, shared contract, passport, service, ledger,
or new test was added. No registration is required.
