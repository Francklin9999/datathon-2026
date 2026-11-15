# Trade follow-on: WITS, UNCTADstat and PortWatch

The two captured slices are annual indicators, not port activity or issuer exposure. Refresh independently from the repository root with `PYTHONPATH=backend .venv/bin/python -m aplomb.world.providers.trade_followon --source wits` or `--source unctad`. The UNCTAD refresh requires the `7z` executable. Source bytes and normalized rows are retained in content-addressed snapshots; rows have no point coordinates and are available only from capture time. Both are now registered in the dataset contract/passports and appear in the country/global observation list with source descriptions. Neither creates a map point or issuer relationship.

## WITS (SRC-113)

The [documented WITS API](https://wits.worldbank.org/witsapiintro.aspx?lang=en) returned data without login or a key. Capture `trade_wits_fuel_exports-2026-11-15-084266aa1efefd2f` contains Canada's 2023 exports of fuels to the world, 143,054,018.299227 **US$ thousand**. This is one reporter, product group, partner and year, not a complete dataset. The response identifies its original source as `WITS - UNSD Comtrade`; the fixed parser verifies the dataset, dimensions, year, unit-labelled indicator, source and observation.

The underlying [UN Comtrade re-dissemination rules](https://uncomtrade.org/docs/re-dissemination-of-data/) govern reuse. Attribute WITS and **Source: UN Comtrade**. The rules describe exemptions for free visualization/analytics and up to 100,000 original records for free extraction or streaming; commercial APIs or streaming require a fee-bearing arrangement. Rights depend on the whole database and intended use. Wider WITS datasets can have other underlying sources and require separate rights review.

- [Fixed API request](https://wits.worldbank.org/API/V1/SDMX/V21/datasource/tradestats-trade/reporter/can/year/2023/partner/wld/product/fuels/indicator/XPRT-TRD-VL?format=JSON)
- Raw SHA-256: `c067197283384425ce20df6ad2980205db61fdced02b65c54ceafe88120c3446`; normalized SHA-256: `084266aa1efefd2f9755d4a005f80894fe459bcb6fdb3ecaebdff8de5c89b149`.

## UNCTADstat (SRC-114, SRC-208)

The [public dataset metadata](https://unctadstat-api.unctad.org/api/reportMetadata/US.ConcentStructIndices) and [bulk archive](https://unctadstat-api.unctad.org/bulkdownload/US.ConcentStructIndices/US_ConcentStructIndices) were accessible without login. The generated user API code requests a client ID and secret, but this separate bulk route works without them. The archive contains 23,746 rows; capture `trade_unctad_concentration-2026-11-15-341fd2bef3772abc` selects two 2025 global export concentration observations: total merchandise 0.155523 and fuels 0.153919. This normalized Herfindahl-Hirschman index measures concentration among exporting countries, not trade value. The parser checks archive member and size, source dataset, selected dimensions, value range, duplicate keys and source missing/footnote flags. This is a bounded sample; shipping and the remaining UNCTAD datasets are not captured.

[UNCTAD Data Hub terms](https://unctadstat.unctad.org/EN/About.html#TERMS_OF_USE) state CC BY 3.0 IGO and allow copying and redistribution of Data Hub data and metadata with attribution to **United Nations Trade and Development Data Hub**. The terms link their [licence text](https://unctadstat.unctad.org/UnctadStatMetadata/Documentation/UNCTAD_CreativeCommonsLicense3.0_IGO_EN.pdf). Preserve attribution, licence and changes disclosure in any downstream use.

- Metadata SHA-256: `94b670f65ec25eab45809cb82347a4bdf9662276727ca14371034998ba345427`; archive SHA-256: `593960e63473bbfadf9db6db5dbf6039b57b1a5e6d8dfec0bb4462d265a49a57`.
- Normalized SHA-256: `341fd2bef3772abcb20d88a98a3d8cca5a69e2705039910fd3408b51b4a13831`.

## PortWatch (SRC-203–205, MASTER-074–076)

The [ports ArcGIS layer](https://services9.arcgis.com/weJ1QsnbMYJlCHdG/ArcGIS/rest/services/PortWatch_ports_database/FeatureServer) and chokepoint table were previously reachable, but the ports item refers to [IMF terms](https://www.imf.org/external/terms.htm), which again returned HTTP 403 on 2026-11-15. Empty copyright text is not a grant of reuse. No source capture is published pending verification of applicable redistribution rights. The chokepoint table has no geometry; a sourced crosswalk would also be required for a map. See `BLOCKERS.md` for the existing parser's scope.

Both new captures loaded with checksum validation through `load_provider_snapshots`; an as-of 2023 query excluded them. `ruff check backend/aplomb/world/providers/trade_followon.py` passed. No new tests were added.
