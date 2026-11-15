"""A precisely scoped, source-indexed partial N-PORT observation.

This small normalized transcript is not a complete issuer file; no inferred holdings,
exchange prices or derivative exposure are reported. See the evidence record for links.
"""
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

from .entities import Evidence
from .overlap import Holding, HoldingsSnapshot, portfolio_lookthrough


def aapu_partial_lookthrough(as_of: date, *, historical: bool = False) -> dict:
    path = Path(__file__).resolve().parent / 'data/sec-nport-aapu-indexed-excerpt.json'
    raw = path.read_bytes()
    transcript = json.loads(raw)
    stamp = datetime.fromisoformat(transcript['retrieved_at'].replace('Z', '+00:00')).astimezone(timezone.utc)
    evidence = Evidence(source_id='fund_sec_nport_indexed_excerpt', url=transcript['source_url'],
                        content_sha256=hashlib.sha256(raw).hexdigest(), available_at=stamp,
                        retrieved_at=stamp, licence='SEC filing; indexed transcript',
                        limitations=tuple(transcript['limitations']))
    fund_id = 'isin:' + transcript['fund_isin']
    snapshot = HoldingsSnapshot(fund_id=fund_id, effective_date=date.fromisoformat(transcript['effective_date']),
        holdings=(Holding(security_id='isin:' + transcript['constituent_isin'],
                          weight_pct=float(transcript['constituent_long_equity_net_asset_pct'])),),
        evidence=evidence, complete=False)
    result = portfolio_lookthrough([Holding(security_id=fund_id, weight_pct=100.0)], [snapshot],
                                   as_of, fund_ids={fund_id}, historical=historical)
    result['fund_series_id'] = transcript['fund_series_id']
    result['fund_class_id'] = transcript['fund_class_id']
    result['fund_mapping_sources'] = [transcript['fund_class_ticker_source'], transcript['fund_ticker_isin_source']]
    result['limitations'].extend(transcript['limitations'])
    return result
