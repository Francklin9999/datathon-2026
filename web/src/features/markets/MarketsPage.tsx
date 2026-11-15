'use client';
import Link from 'next/link';
import { EntityResearch } from './EntityResearch';
import { GoldenCopy } from './GoldenCopy';
import { DefiResearch } from './DefiResearch';
import { CryptoHistory } from './CryptoHistory';
import { EURegulatory } from './EURegulatory';
import { BitcoinNetwork } from './BitcoinNetwork';
import { IssuerEvidence } from './IssuerEvidence';
import { WikidataCandidates } from './WikidataCandidates';
import { CompanyResearch } from './CompanyResearch';
import { BitcoinSentiment } from './BitcoinSentiment';
import { CompanyRegistry } from './CompanyRegistry';
import { DisclosureExample } from './DisclosureExample';
import { FundHoldings } from './FundHoldings';
import { ProviderObservations } from './ProviderObservations';
import { InstrumentMaster } from './InstrumentMaster';
import { OpenFigi } from './OpenFigi';
import { KeyedMarkets } from './KeyedMarkets';
import { RegionalResearch } from './RegionalResearch';
import { SourceAvailability, readySource, useSourceCapabilities } from './SourceAvailability';
import { useState } from 'react';
import type { AssetsResponse, AssetAnalyticsResponse } from '../../contracts/types';
import { useApp } from '../../state/app';
import { useQuery } from '../../state/useQuery';
import { getApiClient } from '../../api/index';
import { Card, PageHeader } from '../../components/common/Page';
import { Loading, ErrorState } from '../../components/common/States';
import { FactScopeProvider, FactChip } from '../../components/common/FactDrawer';
import { fmtPct } from '../../lib/format';

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
  const currency = profile?.reportingCurrency ?? 'CAD';
  // Load the supported universe once; filtering is local and never probes unsupported exchanges.
  const assets = useQuery<AssetsResponse>(sessionId && meta ? `markets|${sessionId}|${meta.dataVersion}` : null,
    signal => getApiClient().assets({ limit: 500 }, signal));
  const analytics = useQuery<AssetAnalyticsResponse>(ticker && sessionId && meta ? `asset|${sessionId}|${meta.dataVersion}|${ticker}|${currency}|${windowCode}` : null,
    signal => getApiClient().assetAnalytics(ticker!, currency, windowCode, signal));
  const items = assets.data?.items.filter(a => `${a.ticker} ${a.name} ${a.market} ${a.assetClass}`.toLowerCase().includes(query.trim().toLowerCase())) ?? [];
  return <>
    <PageHeader title={tr({ en: 'Markets & Stocks', fr: 'Marchés et titres' })}>
      <p className="page-sub">{tr({ en: 'Explore the supported instrument universe and inspect reproducible historical analytics. Snapshot coverage is regional; worldwide navigation does not imply global price coverage.', fr: 'Explorez les instruments pris en charge et leurs analyses historiques reproductibles. La couverture des prix reste régionale.' })}</p>
    </PageHeader>
    <Card title={tr({ en: 'Instrument discovery', fr: 'Recherche de titres' })}>
      <div className="field"><label htmlFor="market-query">{tr({ en: 'Ticker, name, market or asset class', fr: 'Symbole, nom, marché ou catégorie' })}</label><input id="market-query" type="search" value={query} onChange={e => setQuery(e.target.value)} /></div>
      {assets.loading && <Loading />}{assets.error && <ErrorState error={assets.error} onRetry={assets.reload} />}
      <p className="small muted" role="status">{items.length} / {assets.data?.total ?? 0} · {meta?.dataVersion}</p>
      <div className="table-scroll" role="region" aria-label={tr({ en: 'Supported instruments', fr: 'Instruments pris en charge' })} tabIndex={0}>
        <table className="data-table"><thead><tr><th scope="col">{tr({ en: 'Instrument', fr: 'Titre' })}</th><th scope="col">{tr({ en: 'Market', fr: 'Marché' })}</th><th scope="col">{tr({ en: 'Asset class', fr: 'Catégorie' })}</th><th scope="col">{tr({ en: 'Currency', fr: 'Devise' })}</th><th scope="col">{tr({ en: 'History', fr: 'Historique' })}</th></tr></thead><tbody>
          {items.map(a => <tr key={`${a.market}:${a.ticker}`}><th scope="row"><button className="btn ghost" type="button" onClick={() => setTicker(a.ticker)} aria-pressed={ticker === a.ticker}>{a.ticker}</button><span className="block small muted">{a.name}</span></th><td>{a.market}</td><td>{a.assetClass}</td><td>{a.currency}</td><td>{a.history.firstDate} → {a.history.lastDate}</td></tr>)}
        </tbody></table>
      </div>
    </Card>
    <KeyedMarkets />
    <SourceAvailability value={sourceCapabilities.data} loading={sourceCapabilities.loading} error={sourceCapabilities.error} reload={sourceCapabilities.reload} />
    {ready('gleif') && <><EntityResearch /><IssuerEvidence /></>}
    {ready('golden_copy') && <GoldenCopy />}
    {ready('wikidata') && <WikidataCandidates />}
    {ready('sec') && <><CompanyResearch /><FundHoldings /></>}
    {sourceCapabilities.data?.families.some(item => item.id === 'nport_example' && item.state === 'evidence') && <details className="fold section-fold"><summary>{tr({ en: 'Preserved ETF disclosure example', fr: 'Exemple conservé de déclaration de fonds' })}</summary><DisclosureExample /></details>}
    {ready('coinmetrics') && <ProviderObservations secAvailable={ready('sec')} />}
    {ready('dexscreener') && <DefiResearch />}
    {ready('binance_vision') && <CryptoHistory />}
    {ready('eu') && <EURegulatory />}
    {ready('mempool') && <BitcoinNetwork />}
    {ready('sentiment') && <BitcoinSentiment />}
    {ready('registries') && <CompanyRegistry />}
    {ready('master') && <InstrumentMaster showCoinMetrics={ready('coinmetrics')} showWikidata={ready('wikidata')} />}
    {ready('openfigi') && <OpenFigi />}
    {ready('opendart') && <RegionalResearch allowedRegions={['KR']} />}
    {ready('regional') && <RegionalResearch allowedRegions={['JP']} />}
    {ticker && <Card title={ticker}>
      {analytics.loading && <Loading />}{analytics.error && <ErrorState error={analytics.error} onRetry={analytics.reload} />}
      {analytics.data && <FactScopeProvider scope={{ kind: 'local', label: { en: 'Deterministic security analytics', fr: 'Analyse déterministe du titre' }, facts: analytics.data.facts }}>
        <p>{analytics.data.asset.name} · {currency} · {analytics.data.asOf}</p>
        <dl className="kv-list">{Object.entries(metrics).map(([key, label]) => {
          const m = analytics.data!.metrics[key];
          return <div key={key} className="kv"><dt className="k">{tr(label)}</dt><dd className="v">{m?.value != null && m.factId ? <FactChip factId={m.factId} display={fmtPct(m.value, lang)} /> : tr({ en: 'Unavailable', fr: 'Indisponible' })}{m?.unavailableReason && <span className="block small muted">{m.unavailableReason}</span>}</dd></div>;
        })}</dl>
        <p className="small muted">{tr({ en: 'Historical sample only. Adjusted price and FX conventions, availability dates, methods, and source limitations are attached to each metric. No forecast is implied.', fr: 'Échantillon historique seulement. Les méthodes, devises, dates et limites sont jointes à chaque mesure. Aucune prévision n’est impliquée.' })}</p>
        <Link className="btn" href={`/decision-desk/?ticker=${encodeURIComponent(ticker)}`}>{tr({ en: 'Investigate in Decision Desk', fr: 'Étudier au pupitre de décision' })}</Link>{' '}
        <Link href={`/sources/?datasetId=${analytics.data.asset.datasetId}&dataVersion=${analytics.data.dataVersion}`}>{tr({ en: 'Inspect source passport', fr: 'Consulter le passeport' })}</Link>
      </FactScopeProvider>}
    </Card>}
  </>;
}
