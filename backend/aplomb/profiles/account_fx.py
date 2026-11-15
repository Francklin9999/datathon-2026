"""Pinned conversion of user-entered account capital; not an asset valuation model."""
import math

from aplomb.api.errors import ServiceError
from aplomb.contracts.models import AccountValuation
from aplomb.quant.market import MarketData


def convert_account_value(snapshot, native_currency, native_value, reporting_currency, captured_at, as_of=None, *,
                          input_origin=None, input_source=None):
    """Value at the current snapshot, or at an explicitly historical availability cutoff."""
    day = as_of or snapshot.data_as_of
    mode = 'historical' if as_of is not None else 'current'
    if day > snapshot.data_as_of:
        raise ServiceError('validation_error', 'Valuation date cannot exceed the snapshot cutoff')
    gate = snapshot.gate(day, mode)
    market = MarketData(gate, reporting_currency)
    result = market.conversion_at(native_currency, reporting_currency, day)
    if result is None:
        raise ServiceError('insufficient_data', f'No sourced {native_currency}/{reporting_currency} FX conversion at {day}')
    rate, refs = result
    value = native_value * rate
    if not math.isfinite(value) or value <= 0:
        raise ServiceError('validation_error', 'Converted account value must be positive and finite')
    quotes = []
    for dataset, code, observed, available in refs:
        rows = gate.fx(observed, observed).rows if dataset == 'fx_usdcad_daily' else gate.global_fx(code).rows
        row = next(row for row in rows if row['date'] == observed)
        passport = gate.describe(dataset)
        quotes.append({'currency': code, 'cadPerUnit': row['usdcad'] if dataset == 'fx_usdcad_daily' else row['cad_per_unit'],
                       'observedOn': observed, 'availableAt': available,
                       'source': {'datasetId': dataset, 'dataVersion': snapshot.data_version,
                                  'sourceName': passport['source'], 'sourceUrl': passport['sourceUrl'],
                                  'retrievedOn': passport['retrievedOn'], 'licence': passport['licence'], 'rowsRead': 1}})
    receipt = AccountValuation.model_validate({'nativeCurrency': native_currency, 'nativeValue': native_value,
        'nativeValueOrigin': input_origin, 'nativeValueSource': input_source,
        'reportingCurrency': reporting_currency, 'reportingValue': value, 'conversionRate': rate,
        'valuationDate': day, 'mode': mode, 'capturedAt': captured_at, 'dataVersion': snapshot.data_version, 'quotes': quotes})
    receipt.verified_checks = verify_account_valuation(snapshot, receipt)
    return receipt


def verify_account_valuation(snapshot, receipt: AccountValuation) -> list[str]:
    """Independent checks re-read the pinned source rows; caller declarations do not verify values."""
    def require(ok, code):
        if not ok:
            raise ValueError(code)
    require(receipt.data_version == snapshot.data_version, 'ACCOUNT_FX_SNAPSHOT')
    require(receipt.valuation_date <= snapshot.data_as_of and
            (receipt.mode == 'historical' or receipt.valuation_date == snapshot.data_as_of), 'ACCOUNT_FX_CUTOFF')
    gate = snapshot.gate(receipt.valuation_date, receipt.mode)
    required = {receipt.native_currency, receipt.reporting_currency} - {'CAD'}
    if receipt.native_currency == receipt.reporting_currency:
        required = set()
    require(len(receipt.quotes) == len(required) and {q.currency for q in receipt.quotes} == required,
            'ACCOUNT_FX_QUOTE_SET')
    cad = {'CAD': 1.0}
    for quote in receipt.quotes:
        dataset = 'fx_usdcad_daily' if quote.currency == 'USD' else 'fx_boc_global'
        require(quote.source.dataset_id == dataset and quote.source.data_version == snapshot.data_version,
                'ACCOUNT_FX_SOURCE_VERSION')
        passport = gate.describe(dataset)
        require(quote.source.source_name == passport['source'] and quote.source.source_url == passport['sourceUrl']
                and quote.source.retrieved_on == passport['retrievedOn'] and quote.source.licence == passport['licence']
                and quote.source.rows_read == 1, 'ACCOUNT_FX_SOURCE_METADATA')
        rows = gate.fx(None, None).rows if dataset == 'fx_usdcad_daily' else gate.global_fx(quote.currency).rows
        require(bool(rows), 'ACCOUNT_FX_SOURCE_ROW')
        row = rows[-1]
        value = row['usdcad'] if dataset == 'fx_usdcad_daily' else row['cad_per_unit']
        require(quote.observed_on == row['date'] and quote.available_at == row['available_at']
                and quote.cad_per_unit == value, 'ACCOUNT_FX_SOURCE_ROW')
        cad[quote.currency] = value
    expected = 1.0 if not required else cad[receipt.native_currency] / cad[receipt.reporting_currency]
    require(math.isclose(receipt.conversion_rate, expected, rel_tol=1e-12), 'ACCOUNT_FX_DIRECTION')
    require(math.isclose(receipt.reporting_value, receipt.native_value * expected, rel_tol=1e-12),
            'ACCOUNT_FX_MULTIPLICATION')
    return ['ACCOUNT_FX_SNAPSHOT', 'ACCOUNT_FX_CUTOFF', 'ACCOUNT_FX_QUOTE_SET'] + (
        ['ACCOUNT_FX_SOURCE_VERSION', 'ACCOUNT_FX_SOURCE_METADATA', 'ACCOUNT_FX_SOURCE_ROW'] if receipt.quotes else []
    ) + ['ACCOUNT_FX_DIRECTION', 'ACCOUNT_FX_MULTIPLICATION']
