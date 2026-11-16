'use client';
/**
 * "Target allocation": one collapsed card for testing a complete set of final weights instead of a
 * single move. The targets are typed once, then checked instantly by code (RebalancePanel) or
 * analyzed by the AI with an audit (TargetReview).
 */
import { useState } from 'react';
import type { Profile } from '../../contracts/types';
import { useApp } from '../../state/app';
import { useAssetUniverse } from '../../state/useAssetUniverse';
import { checkTickers, targetLineTickers } from '../../lib/tickerCoverage';
import { SupportedUniverse } from '../../components/common/SupportedUniverse';
import { TargetReview } from '../system/TargetReview';
import { RebalancePanel } from './RebalancePanel';

export function TargetAllocation({ profile }: { profile: Profile }) {
  const { tr, feature } = useApp();
  const [text, setText] = useState(() => profile.portfolio.positions.map(p => `${p.ticker} ${p.weightPct}`).join('\n'));
  // Target tickers are checked against the snapshot before any request (the server refuses them after).
  const universe = useAssetUniverse();
  const tickerCheck = checkTickers(targetLineTickers(text), universe, feature('on_demand_tickers'));
  const blocked = tickerCheck.blocking;
  const [locked, setLocked] = useState(false);
  return (
    <details className="section-fold target-fold" id="target-allocation" data-section={tr({ en: 'Target', fr: 'Cible' })} data-tour="target-allocation">
      <summary>
        <span className="target-fold-title">
          {tr({ en: 'Target allocation', fr: 'Allocation cible' })}
          <span className="target-fold-sub">{tr({ en: 'Test a complete set of final weights instead of one move', fr: 'Testez un ensemble complet de poids finaux plutôt qu’un seul mouvement' })}</span>
        </span>
      </summary>
      <div className="fold-body">
        <div className="field">
          <label htmlFor="target-weights">{tr({ en: 'Final weights, one “TICKER PERCENT” per line', fr: 'Poids finaux, un « SYMBOLE POURCENTAGE » par ligne' })}</label>
          <textarea id="target-weights" rows={6} maxLength={4000} value={text} disabled={locked} spellCheck={false}
            onChange={e => setText(e.target.value)} aria-invalid={blocked}
            aria-describedby={`target-weights-hint ${tickerCheck.message ? 'target-weights-issue ' : ''}target-weights-universe`} />
          <span id="target-weights-hint" className="hint">{tr({ en: 'Starts from today’s holdings. List every asset you keep: one left out is sold. The total must be 100%.', fr: 'Part des positions actuelles. Listez chaque actif conservé : un actif omis est vendu. Le total doit faire 100 %.' })}</span>
          {tickerCheck.message && <span id="target-weights-issue" className={blocked ? 'field-error' : 'hint'}>{tr(tickerCheck.message)}</span>}
          <SupportedUniverse id="target-weights-universe" />
        </div>
        <RebalancePanel profile={profile} text={text} blocked={blocked} onBusy={setLocked} />
        <TargetReview profile={profile} text={text} blocked={blocked} />
      </div>
    </details>
  );
}
