'use client';
/**
 * The history of the asset named in the move form (formerly the Markets analytics card): period
 * return, volatility and drawdowns computed by code, each figure a FactChip, plus the source passport.
 * It only asks for a ticker the snapshot lists, so typing a ticker never fires a request per keystroke.
 */
import Link from 'next/link';
import type { AssetAnalyticsResponse, Profile } from '../../contracts/types';
import { getApiClient } from '../../api/index';
import { useApp } from '../../state/app';
import { useQuery } from '../../state/useQuery';
import { useAssetUniverse } from '../../state/useAssetUniverse';
import { Card } from '../../components/common/Page';
import { ErrorState, Loading } from '../../components/common/States';
import { Note } from '../../components/common/Note';
import { FactChip, FactScopeProvider } from '../../components/common/FactDrawer';
import { ASSET_CLASS, WINDOW, labelOf } from '../../lib/labels';
import { fmtPct } from '../../lib/format';

const METRICS = [
  ['return.period', { en: 'Period return', fr: 'Rendement de la période' }],
  ['vol.annualized', { en: 'Annualized volatility', fr: 'Volatilité annualisée' }],
  ['drawdown.max', { en: 'Maximum drawdown', fr: 'Baisse maximale' }],
  ['return.worst_12m', { en: 'Worst 12 months', fr: 'Pires 12 mois' }],
] as const;

export function AssetPanel({ ticker, profile }: { ticker: string; profile: Profile }) {
  const { tr, lang, sessionId, meta, windowSpec, windowCode } = useApp();
  const universe = useAssetUniverse();
  const symbol = ticker.trim().toUpperCase();
  const asset = symbol ? universe.assets.find(a => a.ticker === symbol) ?? null : null;
  const currency = profile.reportingCurrency;
  const subject = asset && sessionId && meta ? `asset|${sessionId}|${meta.dataVersion}|${asset.ticker}|${currency}|` : null;
  const windowKey = JSON.stringify(windowSpec);
  // Same asset, another period: the previous figures stay on screen (dimmed) while the new ones load.
  const analytics = useQuery<AssetAnalyticsResponse>(subject ? `${subject}${windowKey}` : null,
    signal => getApiClient().assetAnalytics(asset!.ticker, currency, windowSpec, signal),
    { keepPreviousFrom: previous => subject !== null && previous.startsWith(subject) });
  const data = analytics.data;

  return (
    <Card id="asset" section={tr({ en: 'Asset', fr: 'Actif' })} tour="asset-panel" title={tr({ en: 'Asset history', fr: 'Historique de l’actif' })}
      info={tr({ en: 'Computed by code from the snapshot’s adjusted prices, in the plan’s currency. A historical sample only: no forecast is implied.', fr: 'Calculé par le code à partir des prix ajustés de l’instantané, dans la devise du plan. Un échantillon historique seulement : aucune prévision n’est impliquée.' })}>
      {!symbol && <Note>{tr({ en: 'Choose an asset in Move details to see how it behaved over the period.', fr: 'Choisissez un actif dans Détails du mouvement pour voir son comportement sur la période.' })}</Note>}
      {symbol && !asset && universe.loading && <Loading />}
      {symbol && !asset && universe.ready && (
        <Note>{tr({ en: `${symbol} has no price history in this snapshot yet.`, fr: `${symbol} n’a pas encore d’historique de prix dans cet instantané.` })}</Note>
      )}
      {symbol && !asset && !universe.ready && !universe.loading && (
        <Note tone="caution">{tr({ en: 'The list of supported assets could not be read, so no history is shown.', fr: 'La liste des actifs pris en charge n’a pas pu être lue : aucun historique n’est affiché.' })}</Note>
      )}
      {asset && analytics.loading && !data && <Loading />}
      {asset && analytics.error && <ErrorState error={analytics.error} onRetry={analytics.reload} />}
      {asset && data && (
        <FactScopeProvider scope={{ kind: 'local', label: { en: 'Deterministic asset history', fr: 'Historique déterministe de l’actif' }, facts: data.facts }}>
          <div className="asset-panel-body" aria-busy={analytics.stale ? true : undefined} data-stale={analytics.stale ? 'true' : undefined}>
            <p className="asset-panel-id">
              <strong className="ticker">{data.asset.ticker}</strong> {data.asset.name}
              <span className="block small muted">
                {labelOf(ASSET_CLASS, data.asset.assetClass, lang)} · {data.asset.market} · {tr({ en: 'in', fr: 'en' })} {currency} · {labelOf(WINDOW, windowCode, lang)} · {tr({ en: 'prices to', fr: 'prix jusqu’au' })} {data.asOf}
              </span>
            </p>
            <dl className="kv-list">{METRICS.map(([key, label]) => {
              const m = data.metrics[key];
              return (
                <div key={key} className="kv">
                  <dt className="k">{tr(label)}</dt>
                  <dd className="v">
                    {m?.value != null && m.factId ? <FactChip factId={m.factId} display={fmtPct(m.value, lang)} /> : tr({ en: 'Unavailable', fr: 'Indisponible' })}
                    {m?.unavailableReason && <span className="block small muted">{m.unavailableReason}</span>}
                  </dd>
                </div>
              );
            })}</dl>
            <p className="row-actions small">
              <Link href={`/sources/?datasetId=${encodeURIComponent(data.asset.datasetId)}&dataVersion=${encodeURIComponent(data.dataVersion)}`}>
                {tr({ en: 'Inspect source passport', fr: 'Consulter le passeport' })}
              </Link>
            </p>
          </div>
        </FactScopeProvider>
      )}
    </Card>
  );
}
