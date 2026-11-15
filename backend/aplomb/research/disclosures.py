"""Bounded official-XML disclosure normalization. Names are labels, never identity joins.

Numbers are reported quantities; no portfolio exposure or complete ownership is inferred.
"""

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree as ET

from .company_detail import cik_id
from .core import ResearchError

REFERENCE_13F = "https://www.sec.gov/files/form_13f_readme.pdf"
REFERENCE_INSIDER = "https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets"
# Form 4 General Instructions, section 8 (transaction codes). Labels only; the reported code is kept verbatim.
TRANSACTION_CODES = {
    "P": "Open market or private purchase", "S": "Open market or private sale",
    "A": "Grant, award or other acquisition from the issuer", "D": "Disposition to the issuer",
    "F": "Payment of exercise price or tax by delivering or withholding securities",
    "I": "Discretionary transaction", "M": "Exercise or conversion of derivative security (exempt)",
    "C": "Conversion of derivative security", "E": "Expiration of short derivative position",
    "H": "Expiration or cancellation of long derivative position with value received",
    "O": "Exercise of out-of-the-money derivative security", "X": "Exercise of in-the-money or at-the-money derivative security",
    "G": "Bona fide gift", "L": "Small acquisition", "W": "Acquisition or disposition by will or laws of descent",
    "Z": "Deposit into or withdrawal from voting trust", "J": "Other acquisition or disposition",
    "K": "Equity swap or similar instrument", "U": "Disposition pursuant to a tender of shares in a change of control",
    "V": "Transaction voluntarily reported earlier than required",
}


def xml_root(text):
    # Same hardening as intelligence/sec_structured.py: any DTD or entity declaration is rejected
    # before parsing, so no internal/external entity expansion can occur.
    if not isinstance(text, str) or len(text.encode()) > 4_000_000 or re.search(r"<!\s*(?:DOCTYPE|ENTITY)", text, re.I):
        raise ResearchError("unsafe_or_oversized_disclosure_xml")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ResearchError("invalid_disclosure_xml") from exc
    if sum(1 for _ in root.iter()) > 100000:
        raise ResearchError("disclosure_xml_element_limit")
    for node in root.iter():
        node.tag = node.tag.rsplit("}", 1)[-1]
    return root


def scalar(node, path, required=True):
    matches = node.findall(path)
    if not matches and not required:
        return None
    if len(matches) != 1 or matches[0].text is None or len(matches[0].text) > 500:
        raise ResearchError("missing_or_ambiguous_disclosure_field")
    return matches[0].text.strip()


def number(node, path, required=True):
    text = scalar(node, path, required)
    if text is None:
        return None
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise ResearchError("invalid_disclosure_number") from exc
    if not value.is_finite() or value < 0:
        raise ResearchError("invalid_disclosure_number")
    return str(value)


def insider_transactions(text, *, issuer_cik, filed):
    filed = date.fromisoformat(filed)
    root = xml_root(text)
    if root.tag != "ownershipDocument" or scalar(root, "documentType") not in ("4", "4/A"):
        raise ResearchError("not_form_four")
    cik = cik_id(scalar(root, "issuer/issuerCik"))
    if cik != cik_id(issuer_cik):
        raise ResearchError("disclosure_issuer_cik_mismatch")
    period = date.fromisoformat(scalar(root, "periodOfReport"))
    if period > filed:
        raise ResearchError("report_after_publication")
    owners = []
    for owner in root.findall("reportingOwner"):
        owners.append({"cik": cik_id(scalar(owner, "reportingOwnerId/rptOwnerCik")),
                       "name": scalar(owner, "reportingOwnerId/rptOwnerName"),
                       "director_reported": scalar(owner, "reportingOwnerRelationship/isDirector", False),
                       "officer_reported": scalar(owner, "reportingOwnerRelationship/isOfficer", False),
                       "ten_percent_owner_reported": scalar(owner, "reportingOwnerRelationship/isTenPercentOwner", False)})
    transactions = []
    for kind, path in (("non_derivative", "nonDerivativeTable/nonDerivativeTransaction"),
                       ("derivative", "derivativeTable/derivativeTransaction")):
        for row in root.findall(path):
            transacted = date.fromisoformat(scalar(row, "transactionDate/value"))
            if transacted > filed:
                raise ResearchError("transaction_after_publication")
            direction = scalar(row, "transactionAmounts/transactionAcquiredDisposedCode/value")
            if direction not in ("A", "D"):
                raise ResearchError("invalid_transaction_direction")
            transactions.append({"kind": kind, "security_title": scalar(row, "securityTitle/value"),
                "transaction_date": str(transacted), "code": scalar(row, "transactionCoding/transactionCode"),
                "code_meaning": TRANSACTION_CODES.get(scalar(row, "transactionCoding/transactionCode"), "See SEC Form 4 instructions"),
                "acquired_or_disposed": direction,
                # Absent when the filer reports the quantity only in a footnote; never defaulted to zero.
                "reported_quantity": number(row, "transactionAmounts/transactionShares/value", False),
                "footnote_ids": sorted({f.get("id") for f in row.iter("footnoteId") if f.get("id")}),
                "underlying_security_title": scalar(row, "underlyingSecurity/underlyingSecurityTitle/value", False),
                "reported_price_per_unit": number(row, "transactionAmounts/transactionPricePerShare/value", False),
                "price_currency": None, "remaining_reported_quantity": number(row, "postTransactionAmounts/sharesOwnedFollowingTransaction/value", False),
                "ownership_nature": scalar(row, "ownershipNature/directOrIndirectOwnership/value", False)})
            if len(transactions) > 1000:
                raise ResearchError("disclosure_transaction_limit")
    footnotes = {}
    for note in root.findall("footnotes/footnote")[:100]:
        if note.get("id"):
            footnotes[note.get("id")] = " ".join("".join(note.itertext()).split())[:600]
    return {"type": "form4", "issuer_cik": cik, "issuer_name": scalar(root, "issuer/issuerName"),
            "issuer_trading_symbol_reported": scalar(root, "issuer/issuerTradingSymbol", False),
            "report_period": str(period), "filed": str(filed), "available_at": str(filed) + "T23:59:59Z",
            "owners": owners, "transactions": transactions, "footnotes": footnotes,
            "data_class": "official_reported", "reference": REFERENCE_INSIDER,
            "limitations": ["Filer-reported transactions, not realtime trades or a recommendation.",
                            "Derivative and indirect quantities are separate; footnotes can change interpretation.",
                            "Currency not declared by these XML fields; no USD assumption.",
                            "Report period or transaction date does not establish earlier public availability."]}


def institutional_holdings(text, *, manager_cik, filed, report_period, cusip_rights=False):
    filed, period = date.fromisoformat(filed), date.fromisoformat(report_period)
    if period > filed:
        raise ResearchError("report_after_publication")
    root = xml_root(text)
    if root.tag != "informationTable":
        raise ResearchError("not_form_13f_information_table")
    rows = []
    # SEC documentation: filings from Jan 3 2023 use nearest dollar; older filings thousands.
    multiplier = 1 if filed >= date(2023, 1, 3) else 1000
    for row in root.findall("infoTable"):
        share_type = scalar(row, "shrsOrPrnAmt/sshPrnamtType")
        if share_type not in ("SH", "PRN"):
            raise ResearchError("invalid_13f_quantity_type")
        cusip = scalar(row, "cusip")
        if not re.fullmatch(r"[A-Z0-9*@#]{9}", cusip):
            raise ResearchError("invalid_13f_identifier")
        raw_value = number(row, "value")
        rows.append({"issuer_label": scalar(row, "nameOfIssuer"), "class_label": scalar(row, "titleOfClass"),
                     # Displayed exactly as the filer reported it; never used as an identity join key
                     # unless a CUSIP licence is configured (cusip_rights).
                     "cusip_as_reported": cusip, "cusip_identity_join": bool(cusip_rights),
                     "cusip": cusip if cusip_rights else None, "exact_security_mapping": "unresolved",
                     "reported_value_usd": format(Decimal(raw_value) * multiplier, "f"), "source_value": raw_value,
                     "source_value_multiplier": multiplier, "quantity": number(row, "shrsOrPrnAmt/sshPrnamt"),
                     "quantity_type": share_type, "put_call": scalar(row, "putCall", False),
                     "discretion": scalar(row, "investmentDiscretion", False),
                     "voting_sole": number(row, "votingAuthority/Sole", False),
                     "voting_shared": number(row, "votingAuthority/Shared", False),
                     "voting_none": number(row, "votingAuthority/None", False)})
        if len(rows) > 10000:
            raise ResearchError("disclosure_holding_limit")
    return {"type": "form13f", "manager_cik": cik_id(manager_cik), "report_period": str(period),
            "filed": str(filed), "available_at": str(filed) + "T23:59:59Z", "holdings": rows,
            "unit_reference": REFERENCE_13F, "data_class": "official_reported",
            "value_unit_rule": ("Filed on/after 2023-01-03: value reported to the nearest dollar."
                                if multiplier == 1 else "Filed before 2023-01-03: value reported in thousands of dollars; multiplied by 1000."),
            "limitations": ["Delayed manager-reported positions; not current or complete beneficial ownership.",
                            "Confidential treatment, amendments, short positions and instrument scope limit coverage.",
                            "No issuer or listing is resolved from a name or an unlicensed CUSIP crosswalk.",
                            "The information table does not itself prove manager identity; bind it to its SEC accession."]}


def summarize_holdings(parsed, top=25):
    """Code-computed totals over the reported rows; weights are shares of this table's reported total only."""
    rows = parsed["holdings"]
    total = sum((Decimal(r["reported_value_usd"]) for r in rows), Decimal(0))
    ranked = sorted(rows, key=lambda r: (-Decimal(r["reported_value_usd"]), r["issuer_label"], r["class_label"]))
    shown = []
    for row in ranked[:top]:
        weight = (Decimal(row["reported_value_usd"]) * 100 / total).quantize(Decimal("0.01")) if total else None
        shown.append({**row, "pct_of_reported_total": format(weight, "f") if weight is not None else None})
    return {**{k: v for k, v in parsed.items() if k != "holdings"},
            "holdings": shown, "row_count": len(rows), "rows_shown": len(shown),
            "reported_total_usd": format(total, "f"),
            "method": "Sum of reported values in this information table; percentages are of that sum, "
                      "not of the manager's assets or any security's float."}
