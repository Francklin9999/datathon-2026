'use client';
/**
 * Instrument discovery (moved from the Markets page): search the supported universe locally, pick an
 * instrument and read its reproducible historical analytics for the selected period.
 */
import Link from 'next/link';
import { useDeferredValue, useEffect, useMemo, useRef, useState } from 'react';
import type { AssetsResponse, AssetAnalyticsResponse } from '../../contracts/types';
import { useApp } from '../../state/app';
import { useQuery } from '../../state/useQuery';
import { ASSET_UNIVERSE_LIMIT, assetUniverseKey } from '../../state/useAssetUniverse';
import { fold } from '../../lib/suggest';
import { universeMarkets } from '../../lib/universe';
import { instrumentCountLine, noMatchingInstrument, showAllInstruments } from '../../lib/tickerCoverage';
import { getApiClient } from '../../api/index';
import { Card } from '../../components/common/Page';
import { Loading, ErrorState } from '../../components/common/States';
import { FactScopeProvider, FactChip } from '../../components/common/FactDrawer';
import { fmtPct } from '../../lib/format';
import { ASSET_CLASS, WINDOW, labelOf } from '../../lib/labels';
import { WindowControl } from '../../components/shell/TopBar';

const metrics = {
  'return.period': { en: 'Period return', fr: 'Rendement de la période' },
  'vol.annualized': { en: 'Annualized volatility', fr: 'Volatilité annualisée' },
  'drawdown.max': { en: 'Maximum drawdown', fr: 'Baisse maximale' },
  'return.worst_12m': { en: 'Worst rolling 12-month return', fr: 'Pire rendement glissant sur 12 mois' },
};

export function InstrumentDiscovery() {
  const { tr, lang, sessionId, meta, profile, windowCode } = useApp();
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
  // The supported universe is read once (the same read the search fields share); filtering is local
  // and never probes unsupported exchanges.
  const assets = useQuery<AssetsResponse>(sessionId && meta ? assetUniverseKey(meta.dataVersion) : null,
    signal => getApiClient().assets({ limit: ASSET_UNIVERSE_LIMIT }, signal));
  const analyticsBase = ticker && sessionId && meta ? `asset|${sessionId}|${meta.dataVersion}|${ticker}|${currency}|` : null;
  const analytics = useQuery<AssetAnalyticsResponse>(analyticsBase ? `${analyticsBase}${windowCode}` : null,
    signal => getApiClient().assetAnalytics(ticker!, currency, windowCode, signal),
    // Same instrument, another period: keep the figures on screen while the new period loads.
    { keepPreviousFrom: previous => analyticsBase !== null && previous.startsWith(analyticsBase) });
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
    <Card title={tr({ en: 'Instrument discovery', fr: 'Recherche de titres' })} actions={<WindowControl />}>
      <div className="field"><label htmlFor="labs-instrument-query">{tr({ en: 'Ticker, name, market or asset class', fr: 'Symbole, nom, marché ou catégorie' })}</label><input id="labs-instrument-query" type="search" value={query} onChange={e => setQuery(e.target.value)} /></div>
      {assets.loading && <Loading />}{assets.error && <ErrorState error={assets.error} onRetry={assets.reload} />}
      {assets.data && <p className="small muted" role="status">{tr(instrumentCountLine(items.length, total, meta?.dataVersion ?? null))}</p>}
      {noMatch && <div className="state state-empty">
        <p className="muted">{tr(noMatchingInstrument(deferredQuery, total, meta?.dataVersion ?? null, markets))}</p>
        <button type="button" className="btn ghost" onClick={() => setQuery('')}>{tr(showAllInstruments(total))}</button>
      </div>}
      {!noMatch && assets.data && <div className="table-scroll" role="region" aria-label={tr({ en: 'Supported instruments', fr: 'Instruments pris en charge' })} tabIndex={0}>
        <table className="data-table"><thead><tr><th scope="col">{tr({ en: 'Instrument', fr: 'Titre' })}</th><th scope="col">{tr({ en: 'Market', fr: 'Marché' })}</th><th scope="col">{tr({ en: 'Asset class', fr: 'Catégorie' })}</th><th scope="col">{tr({ en: 'Currency', fr: 'Devise' })}</th><th scope="col">{tr({ en: 'History', fr: 'Historique' })}</th></tr></thead><tbody>
          {items.map(a => <tr key={`${a.market}:${a.ticker}`}><th scope="row"><button className="btn ghost" type="button" onClick={() => setTicker(a.ticker)} aria-pressed={ticker === a.ticker}>{a.ticker}</button><span className="block small muted">{a.name}</span></th><td>{a.market}</td><td>{labelOf(ASSET_CLASS, a.assetClass, lang)}</td><td>{a.currency}</td><td>{a.history.firstDate} → {a.history.lastDate}</td></tr>)}
        </tbody></table>
      </div>}
    </Card>
    {ticker && <div ref={resultPanel} tabIndex={-1} role="region" aria-labelledby="labs-instrument-analytics-title"><Card id="labs-instrument-analytics" title={ticker}>
      {analytics.loading && !analytics.data && <Loading />}{analytics.error && <ErrorState error={analytics.error} onRetry={analytics.reload} />}
      {analytics.data && <FactScopeProvider scope={{ kind: 'local', label: { en: 'Deterministic security analytics', fr: 'Analyse déterministe du titre' }, facts: analytics.data.facts }}>
        <div aria-busy={analytics.stale ? 'true' : undefined}>
          <p>{analytics.data.asset.name} · {currency} · {analytics.data.asOf}</p>
          <p>{tr({ en: 'Analysis period', fr: 'Période d’analyse' })}: <strong>{labelOf(WINDOW, windowCode, lang)}</strong></p>
          <dl className="kv-list">{Object.entries(metrics).map(([key, label]) => {
            const m = analytics.data!.metrics[key];
            return <div key={key} className="kv"><dt className="k">{tr(label)}</dt><dd className="v">{m?.value != null && m.factId ? <FactChip factId={m.factId} display={fmtPct(m.value, lang)} /> : tr({ en: 'Unavailable', fr: 'Indisponible' })}{m?.unavailableReason && <span className="block small muted">{m.unavailableReason}</span>}</dd></div>;
          })}</dl>
          <p className="small muted">{tr({ en: 'Historical sample only; each figure carries its method, currency, dates and source limits. No forecast is implied.', fr: 'Échantillon historique seulement; chaque chiffre porte sa méthode, sa devise, ses dates et les limites de sa source. Aucune prévision n’est impliquée.' })}</p>
          <div className="labs-actions">
            <Link className="btn" href={`/decision-desk/?ticker=${encodeURIComponent(ticker)}`}>{tr({ en: 'Study in Decide', fr: 'Étudier dans Décider' })}</Link>
            <Link className="btn ghost" href={`/sources/?datasetId=${analytics.data.asset.datasetId}&dataVersion=${analytics.data.dataVersion}`}>{tr({ en: 'Source passport', fr: 'Passeport de la source' })}</Link>
          </div>
        </div>
      </FactScopeProvider>}
    </Card></div>}
  </>;
}
