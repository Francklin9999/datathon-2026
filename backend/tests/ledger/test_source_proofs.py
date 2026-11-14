"""Independent rejection tests for source-backed numeric verification."""
import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from aplomb.ledger import DocumentRef, Ledger
from aplomb.research import ResearchContext, ResearchService, Response
from aplomb.research.numeric import document_ref, fact_input

NOW = datetime(2026, 11, 14, tzinfo=UTC)
URL = ('https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/'
       'en.wikipedia.org/all-access/user/Apple_Inc./daily/2025101500/2026111300')
RAW = Path(__file__).parents[1] / 'research/fixtures/captured/wikimedia-395.json'


class Capture:
    def __init__(self, text):
        self.text = text

    def get(self, url, **kwargs):
        return Response(200, {'content-type': 'application/json'}, self.text.encode())


def setup(text=None):
    rc = ResearchContext('proof-run', date(2026, 11, 14))
    service = ResearchService(Capture(text or RAW.read_text()), lambda: NOW,
                              resolver=lambda *a, **kw: [(2, 1, 6, '', ('8.8.8.8', 443))])
    doc = service.fetch(URL, rc)
    fact = fact_input(doc, rc, value=0.8359944473541175, unit='ratio',
                      subject_type='event', subject_id='Apple_Inc.', variant='series',
                      label='Attention', metric='attention.pageviews_ratio')
    return Ledger(rc.run_id, str(rc.as_of)), doc, fact


@pytest.mark.parametrize('mutation', ['value', 'subject', 'unit', 'source', 'cross_run',
                                     'missing_day', 'duplicate_day', 'wrong_article', 'bool_count'])
def test_attention_proof_cannot_certify_forged_claim_and_rolls_back(mutation):
    source = json.loads(RAW.read_text())
    if mutation == 'missing_day':
        source['items'].pop()
    elif mutation == 'duplicate_day':
        source['items'][-1] = source['items'][0]
    elif mutation == 'wrong_article':
        source['items'][0]['article'] = 'Microsoft'
    elif mutation == 'bool_count':
        source['items'][0]['views'] = True
    ledger, doc, fact = setup(json.dumps(source))
    ref = document_ref(doc)
    if mutation == 'value':
        fact['value'] = 7
    elif mutation == 'subject':
        fact['subject']['id'] = 'Microsoft'
    elif mutation == 'unit':
        fact['unit'] = 'pct'
    elif mutation == 'source':
        fact['sources'][0]['source_url'] = 'https://www.sec.gov/forged'
    elif mutation == 'cross_run':
        ref = DocumentRef(ref.reference, ref.text, ref.source_url, 'different-run')
    with pytest.raises(ValueError):
        ledger.add_pageviews_ratio(fact, ref, article='Apple_Inc.')
    assert not ledger.export().facts and not ledger.export().evidence
    assert not ledger.checkpoint()['documents']


def test_repeated_proof_reuses_ids_and_preserves_checkpoint():
    ledger, doc, fact = setup()
    first = ledger.add_pageviews_ratio(fact, document_ref(doc), article='Apple_Inc.')
    second = ledger.add_pageviews_ratio(fact, document_ref(doc), article='Apple_Inc.')
    assert first == second
    assert ledger.get_fact(first).available_at is None
    assert len(ledger.export().facts) == 2
    restored = Ledger.restore(ledger.run_id, ledger.as_of, ledger.checkpoint())
    assert restored.export().digest() == ledger.export().digest()


def test_transaction_rolls_back_a_successful_proof_if_later_registration_fails():
    ledger, doc, fact = setup()
    with pytest.raises(ValueError):
        with ledger.transaction():
            ledger.add_pageviews_ratio(fact, document_ref(doc), article='Apple_Inc.')
            ledger.add_pageviews_ratio({**fact, 'value': -1}, document_ref(doc), article='Apple_Inc.')
    assert not ledger.export().facts
    assert not ledger.checkpoint()['documents']


@pytest.mark.parametrize('mutation', ['value', 'unit', 'cik', 'future', 'duplicate_key'])
def test_sec_structured_proof_rejects_invalid_currency_record(mutation):
    source = {'cik': 320193, 'facts': {'us-gaap': {'Assets': {'units': {'USD': [
        {'val': 42, 'end': '2026-09-30', 'filed': '2026-10-30'}]}}}}}
    if mutation == 'cik':
        source['cik'] = 123
    if mutation == 'future':
        source['facts']['us-gaap']['Assets']['units']['USD'][0]['filed'] = '2027-01-01'
    text = json.dumps(source)
    if mutation == 'duplicate_key':
        text = text.replace('"val": 42', '"val": 42, "val": 43')
    ledger, doc, fact = setup()
    url = 'https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json'
    ref = DocumentRef('sec-record', text, url, ledger.run_id)
    fact.update(metric='quote.figure', value=43 if mutation == 'value' else 42,
                unit='cad' if mutation == 'unit' else 'usd', currency='USD',
                subject={'type': 'asset', 'id': '0000320193'})
    fact['sources'][0]['source_url'] = url
    with pytest.raises(ValueError):
        ledger.add_source_fact(fact, ref, {'format': 'sec_companyfacts', 'concept': 'Assets',
                                          'unit': 'USD', 'row_index': 0})
    assert not ledger.export().facts and not ledger.checkpoint()['documents']


@pytest.mark.parametrize('mutation', ['value', 'unit_header', 'duplicate_id', 'date', 'host'])
def test_csv_proof_rejects_ambiguous_or_forged_weight(mutation):
    text = 'Holdings date,2026-11-14\nTicker,Weight (%)\nAAPL,4.2\n'
    header = 'Weight (%)'
    if mutation == 'unit_header':
        text, header = text.replace('Weight (%)', 'Weight'), 'Weight'
    if mutation == 'duplicate_id':
        text += 'AAPL,4.2\n'
    if mutation == 'date':
        text = text.replace('2026-11-14', '2026-11-13')
    url = 'https://www.ishares.com/file?fileType=csv'
    if mutation == 'host':
        url = 'https://www.sec.gov/file'
    ledger, doc, fact = setup()
    ref = DocumentRef('issuer-record', text, url, ledger.run_id)
    fact.update(metric='quote.figure', value=8.4 if mutation == 'value' else 4.2,
                unit='pct', currency=None, subject={'type': 'asset', 'id': 'AAPL'})
    fact['sources'][0]['source_url'] = url
    with pytest.raises(ValueError):
        ledger.add_source_fact(fact, ref, {'format': 'issuer_holdings_csv', 'identifier': 'AAPL',
            'effective_date': '2026-11-14', 'identifier_column': 'Ticker', 'weight_column': header})
    assert not ledger.export().facts and not ledger.checkpoint()['documents']
