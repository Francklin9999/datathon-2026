"""Code-owned structured source proof assembly; ledger independently reparses source bytes."""
from urllib.parse import urlsplit

from .core import ResearchError, policy_for


def document_ref(document):
    from aplomb.ledger import DocumentRef
    return DocumentRef(document.document_id, document.text, document.canonical_url, document.run_id)


def fact_input(document, context, *, value, unit, subject_id, variant, label,
               metric="quote.figure", limitations=None, subject_type="asset"):
    policy = policy_for(urlsplit(document.canonical_url).hostname)
    return {
        "kind": "evidence", "metric": metric,
        "label": {"en": label, "fr": label}, "value": value, "unit": unit,
        "currency": "USD" if unit == "usd" else "CAD" if unit == "cad" else None,
        "subject": {"type": subject_type, "id": subject_id, "variant": variant},
        "period": None, "window": None, "as_of": str(context.as_of), "available_at": None,
        "method": {"id": "M_QUOTE_VERBATIM", "description": {"en": "Structured source lookup", "fr": "Lecture de source structurée"}, "params": {}},
        "inputs": [], "n_obs": None,
        "sources": [{"dataset_id": "research_documents", "data_version": context.data_version,
                     "source_name": policy.publisher, "source_url": document.canonical_url,
                     "retrieved_on": str(document.retrieved_at.date()), "licence": policy.licence,
                     "rows_read": None}],
        "limitations": limitations or [], "verification": {"status": "unverified", "checks": []},
        "created_by": "research",
    }


def fact_value(ledger, fact_id):
    fact = ledger.get_fact(fact_id)
    if fact.verification.status != "verified":
        raise ResearchError("structured_source_not_verified")
    return {"value": fact.value, "unit": fact.unit, "factId": fact_id}


def source_evidence(service, document, context, ledger, *, type, title, subject_id):
    """An excerpt proves source capture; structured fact proof supports the numeric claim."""
    quote = document.text[:350]
    if not quote.strip():
        raise ResearchError("empty_source_document")
    return service.save_evidence({"type": type, "title": title, "publisher": "computed",
        "url": document.canonical_url, "quote": quote,
        "claim": {"en": "Captured source excerpt; numerical facts are verified separately against structured records.",
                  "fr": "Extrait de source conservé; les faits numériques sont vérifiés séparément dans les données structurées."},
        "subject": {"type": "asset", "id": subject_id}}, document.document_id, context, ledger)
