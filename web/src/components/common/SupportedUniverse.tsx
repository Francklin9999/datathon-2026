'use client';
/**
 * "31 supported instruments": a disclosure placed next to a ticker field, listing what the pinned
 * snapshot covers (ticker, name, market, currency). Renders nothing until the universe read has
 * completed, so a slow or failed read never shows a wrong list.
 */
import { useMemo } from 'react';
import { supportedCountLabel, supportedUniverseHint, universeMarkets, ON_DEMAND_OFF } from '../../lib/universe';
import { useApp } from '../../state/app';
import { useAssetUniverse } from '../../state/useAssetUniverse';

export function SupportedUniverse({ id, className }: {
  /** For the field's aria-describedby: set on the short summary only, so a screen reader does not
   *  read the whole instrument list as the field's description when the disclosure is open. */
  id?: string | undefined;
  className?: string | undefined;
}) {
  const { tr, feature } = useApp();
  const universe = useAssetUniverse();
  const markets = useMemo(() => universeMarkets(universe.assets), [universe.assets]);
  if (!universe.ready || !universe.dataVersion) return null;
  return (
    <details className={`supported-universe small${className ? ` ${className}` : ''}`}>
      <summary id={id}>{tr(supportedCountLabel(universe.total))}</summary>
      <p className="muted">{tr(supportedUniverseHint(universe.total, universe.dataVersion, markets))}</p>
      {/* The list scrolls inside a fixed height: focusable so a keyboard can scroll it. */}
      <ul className="supported-universe-list" tabIndex={0} aria-label={tr(supportedCountLabel(universe.total))}>
        {universe.assets.map(asset => (
          <li key={`${asset.market}:${asset.ticker}`}>
            <span className="mono">{asset.ticker}</span> — {asset.name} <span className="muted">· {asset.market} · {asset.currency}</span>
          </li>
        ))}
      </ul>
      {!feature('on_demand_tickers') && <p className="muted">{tr(ON_DEMAND_OFF)}</p>}
    </details>
  );
}
