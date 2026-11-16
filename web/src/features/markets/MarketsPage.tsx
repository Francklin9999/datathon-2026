'use client';
import Link from 'next/link';
import { EntityResearch } from './EntityResearch';
import { GoldenCopy } from './GoldenCopy';
import { DefiResearch } from './DefiResearch';
import { CryptoHistory } from './CryptoHistory';
import { EURegulatory } from './EURegulatory';
import { IssuerEvidence } from './IssuerEvidence';
import { WikidataCandidates } from './WikidataCandidates';
import { BitcoinSentiment } from './BitcoinSentiment';
import { CompanyRegistry } from './CompanyRegistry';
import { ProviderObservations } from './ProviderObservations';
import { InstrumentMaster } from './InstrumentMaster';
import { OpenFigi } from './OpenFigi';
import { KeyedMarkets } from './KeyedMarkets';
import { RegionalResearch } from './RegionalResearch';
import { SourceAvailability, readySource, useSourceCapabilities } from './SourceAvailability';
import { useDeferredValue, useEffect, useMemo, useRef, useState } from 'react';
import type { AssetsResponse, AssetAnalyticsResponse } from '../../contracts/types';
import { useApp } from '../../state/app';
import { useQuery } from '../../state/useQuery';
import { ASSET_UNIVERSE_LIMIT, assetUniverseKey } from '../../state/useAssetUniverse';
import { fold } from '../../lib/suggest';
import { universeMarkets } from '../../lib/universe';
import { instrumentCountLine, noMatchingInstrument, showAllInstruments } from '../../lib/tickerCoverage';
import { getApiClient } from '../../api/index';
import { Card, PageHeader } from '../../components/common/Page';
import { Loading, ErrorState } from '../../components/common/States';
import { FactScopeProvider, FactChip } from '../../components/common/FactDrawer';
import { fmtPct } from '../../lib/format';
import { WINDOW, labelOf } from '../../lib/labels';
import { WindowControl } from '../../components/shell/TopBar';

const metrics = {
  'return.period': { en: 'Period return', fr: 'Rendement de la période' },
  'vol.annualized': { en: 'Annualized volatility', fr: 'Volatilité annualisée' },
  'drawdown.max': { en: 'Maximum drawdown', fr: 'Baisse maximale' },
  'return.worst_12m': { en: 'Worst rolling 12-month return', fr: 'Pire rendement glissant sur 12 mois' },
};

export function MarketsPage() {
  const { tr, lang, sessionId, meta, profile, windowCode } = useApp();
  const sourceCapabilities = useSourceCapabilities();
  const ready = (id: string) => readySource(sourceCapabilities.data, id);
  const [query, setQuery] = useState('');
  const [ticker, setTicker] = useState<string | null>(null);
  const resultPanel = useRef<HTMLDivElement | null>(null);
  const currency = profile?.reportingCurrency ?? 'CAD';
  useEffect(() => {
    const panel = resultPanel.current;
    if (!ticker || !panel) return;
    panel.focus({ preventScroll: true });
    const headerBottom = document.querySelector('.topbar')?.getBoundingClientRect().bottom ?? 0;
    window.scrollBy({ top: panel.getBoundingClientRect().top - headerBottom - 16 });
  }, [ticker]);
  // Load the supported universe once (the same read the search fields share); filtering is local and
  // never probes unsupported exchanges.
  const assets = useQuery<AssetsResponse>(sessionId && meta ? assetUniverseKey(meta.dataVersion) : null,
    signal => getApiClient().assets({ limit: ASSET_UNIVERSE_LIMIT }, signal));
  const analytics = useQuery<AssetAnalyticsResponse>(ticker && sessionId && meta ? `asset|${sessionId}|${meta.dataVersion}|${ticker}|${currency}|${windowCode}` : null,
    signal => getApiClient().assetAnalytics(ticker!, currency, windowCode, signal));
  // Typing stays instant: the searched text is prepared once per universe and the table follows a
  // deferred query (case and accents ignored).
  const searchable = useMemo(() => (assets.data?.items ?? []).map(a => ({ asset: a, text: fold(`${a.ticker} ${a.name} ${a.market} ${a.assetClass}`) })), [assets.data]);
  const deferredQuery = useDeferredValue(query);
  const needle = fold(deferredQuery.trim());
  const items = useMemo(() => searchable.filter(row => !needle || row.text.includes(needle)).map(row => row.asset), [searchable, needle]);
  const markets = useMemo(() => universeMarkets(assets.data?.items ?? []), [assets.data]);
  const total = assets.data?.total ?? 0;
  // A search that matches nothing says what the snapshot covers instead of showing an empty table.
  const noMatch = assets.data !== null && needle !== '' && items.length === 0;
  return <>
    <PageHeader actions={<WindowControl />} title={tr({ en: 'Markets & Stocks', fr: 'Marchés et titres' })}>
      <p className="page-sub">{tr({ en: 'Explore the supported instrument universe and inspect reproducible historical analytics. Snapshot coverage is regional; worldwide navigation does not imply global price coverage.', fr: 'Explorez les instruments pris en charge et leurs analyses historiques reproductibles. La couverture de l’instantané est régionale ; la navigation mondiale n’implique pas une couverture mondiale des prix.' })}</p>
    </PageHeader>
    <Card title={tr({ en: 'Instrument discovery', fr: 'Recherche de titres' })}>
      <div className="field"><label htmlFor="market-query">{tr({ en: 'Ticker, name, market or asset class', fr: 'Symbole, nom, marché ou catégorie' })}</label><input id="market-query" type="search" value={query} onChange={e => setQuery(e.target.value)} /></div>
      {assets.loading && <Loading />}{assets.error && <ErrorState error={assets.error} onRetry={assets.reload} />}
      {assets.data && <p className="small muted" role="status">{tr(instrumentCountLine(items.length, total, meta?.dataVersion ?? null))}</p>}
      {noMatch && <div className="state state-empty">
        <p className="muted">{tr(noMatchingInstrument(deferredQuery, total, meta?.dataVersion ?? null, markets))}</p>
        <button type="button" className="btn ghost" onClick={() => setQuery('')}>{tr(showAllInstruments(total))}</button>
      </div>}
      {!noMatch && <div className="table-scroll" role="region" aria-label={tr({ en: 'Supported instruments', fr: 'Instruments pris en charge' })} tabIndex={0}>
        <table className="data-table"><thead><tr><th scope="col">{tr({ en: 'Instrument', fr: 'Titre' })}</th><th scope="col">{tr({ en: 'Market', fr: 'Marché' })}</th><th scope="col">{tr({ en: 'Asset class', fr: 'Catégorie' })}</th><th scope="col">{tr({ en: 'Currency', fr: 'Devise' })}</th><th scope="col">{tr({ en: 'History', fr: 'Historique' })}</th></tr></thead><tbody>
          {items.map(a => <tr key={`${a.market}:${a.ticker}`}><th scope="row"><button className="btn ghost" type="button" onClick={() => setTicker(a.ticker)} aria-pressed={ticker === a.ticker}>{a.ticker}</button><span className="block small muted">{a.name}</span></th><td>{a.market}</td><td>{a.assetClass}</td><td>{a.currency}</td><td>{a.history.firstDate} → {a.history.lastDate}</td></tr>)}
        </tbody></table>
      </div>}
    </Card>
    {ticker && <div ref={resultPanel} tabIndex={-1} role="region" aria-labelledby="market-analytics-title"><Card id="market-analytics" title={ticker}>
      {analytics.loading && <Loading />}{analytics.error && <ErrorState error={analytics.error} onRetry={analytics.reload} />}
      {analytics.data && <FactScopeProvider scope={{ kind: 'local', label: { en: 'Deterministic security analytics', fr: 'Analyse déterministe du titre' }, facts: analytics.data.facts }}>
        <p>{analytics.data.asset.name} · {currency} · {analytics.data.asOf}</p>
        <p>{tr({ en: 'Analysis period', fr: 'Période d’analyse' })}: <strong>{labelOf(WINDOW, windowCode, lang)}</strong></p>
        <dl className="kv-list">{Object.entries(metrics).map(([key, label]) => {
          const m = analytics.data!.metrics[key];
          return <div key={key} className="kv"><dt className="k">{tr(label)}</dt><dd className="v">{m?.value != null && m.factId ? <FactChip factId={m.factId} display={fmtPct(m.value, lang)} /> : tr({ en: 'Unavailable', fr: 'Indisponible' })}{m?.unavailableReason && <span className="block small muted">{m.unavailableReason}</span>}</dd></div>;
        })}</dl>
        <p className="small muted">{tr({ en: 'Historical sample only. Adjusted price and FX conventions, availability dates, methods, and source limitations are attached to each metric. No forecast is implied.', fr: 'Échantillon historique seulement. Les méthodes, devises, dates et limites sont jointes à chaque mesure. Aucune prévision n’est impliquée.' })}</p>
        <Link className="btn" href={`/decision-desk/?ticker=${encodeURIComponent(ticker)}`}>{tr({ en: 'Investigate in Decision Desk', fr: 'Étudier au pupitre de décision' })}</Link>{' '}
        <Link href={`/sources/?datasetId=${analytics.data.asset.datasetId}&dataVersion=${analytics.data.dataVersion}`}>{tr({ en: 'Inspect source passport', fr: 'Consulter le passeport' })}</Link>
      </FactScopeProvider>}
    </Card></div>}
    <KeyedMarkets />
    <SourceAvailability value={sourceCapabilities.data} loading={sourceCapabilities.loading} error={sourceCapabilities.error} reload={sourceCapabilities.reload} />
    {ready('gleif') && <><EntityResearch /><IssuerEvidence /></>}
    {ready('golden_copy') && <GoldenCopy />}
    {ready('wikidata') && <WikidataCandidates />}
    {ready('coinmetrics') && <ProviderObservations />}
    {ready('dexscreener') && <DefiResearch />}
    {ready('binance_vision') && <CryptoHistory />}
    {ready('eu') && <EURegulatory />}
    {ready('sentiment') && <BitcoinSentiment />}
    {ready('registries') && <CompanyRegistry />}
    {ready('master') && <InstrumentMaster showCoinMetrics={ready('coinmetrics')} showWikidata={ready('wikidata')} />}
    {ready('openfigi') && <OpenFigi />}
    {ready('opendart') && <RegionalResearch allowedRegions={['KR']} />}
    {ready('regional') && <RegionalResearch allowedRegions={['JP']} />}
  </>;
}
