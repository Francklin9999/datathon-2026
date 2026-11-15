'use client';
/**
 * Result building blocks (T14): verdict header, boundary wording, before/after snapshot, funding
 * comparison and scenario cards. Reused by Decision Desk (preview and run), Evidence & Audit and,
 * per web/SPEC.md §2, by T15 pages instead of defining alternate statuses.
 */
import type {
  Funding, FundingOption, Lang, PortfolioSnapshot, Scenario, Verdict, VerdictCounts,
} from '../../contracts/types';
import { ASSET_GROUP, FUNDING_MODE, SCENARIO_KIND, labelOf } from '../../lib/labels';
import { factIdFor, fmtMoney, fmtPct, fmtPts, fmtSignedPct } from '../../lib/format';
import { useApp } from '../../state/app';
import { CountsLine, VerdictBadge } from '../common/Badges';
import { FactChip } from '../common/FactDrawer';
import { RuleTable } from './RuleTable';

export function VerdictHeader({ verdict, counts }: { verdict: Verdict; counts: VerdictCounts }) {
  const { tr } = useApp();
  return (
    <div className="verdict-header">
      <VerdictBadge verdict={verdict} large />
      <CountsLine counts={counts} />
      {counts.nee > 0 && (
        <p className="small nee-reason">
          {tr({ en: 'Some checks lack evidence; passing numbers do not show that those rules are met.', fr: 'Certaines vérifications manquent de preuves ; des chiffres conformes ne montrent pas que ces règles sont respectées.' })}
        </p>
      )}
    </div>
  );
}

/** "Largest size before the first rule conflict", followed by evidence/tension status (DESIGN.md). */
export function BoundaryNote({ sizePct, counts, baselineConflict, countsAt = 'requested' }: {
  sizePct: number | null; counts?: VerdictCounts | null; baselineConflict?: boolean;
  /** Which size `counts` describes: the requested move (a /check result) or the boundary scenario. */
  countsAt?: 'requested' | 'boundary';
}) {
  const { tr, lang } = useApp();
  if (baselineConflict) {
    return (
      <p className="boundary">
        {tr({ en: 'The current portfolio already conflicts with at least one rule before any move, so no size is free of conflict.', fr: 'Le portefeuille actuel est déjà en conflit avec au moins une règle avant tout mouvement ; aucune taille n’est exempte de conflit.' })}
      </p>
    );
  }
  if (sizePct === null) return null;
  return (
    <p className="boundary">
      <span className="eyebrow block">{tr({ en: 'Largest size before the first rule conflict', fr: 'Taille maximale avant le premier conflit de règle' })}</span>
      <strong className="boundary-value num">{fmtPts(sizePct, lang)}</strong>
      <span className="small muted block">
        {tr({ en: 'Tension or missing evidence can remain at this size.', fr: 'Des tensions ou preuves manquantes peuvent subsister à cette taille.' })}
        {counts && (counts.tension > 0 || counts.nee > 0) && (
          <> {countsAt === 'boundary'
            ? tr({ en: `At this size: ${counts.tension} tension, ${counts.nee} not enough evidence.`, fr: `À cette taille : ${counts.tension} tension(s), ${counts.nee} preuve(s) insuffisante(s).` })
            : tr({ en: `At the requested size: ${counts.tension} tension, ${counts.nee} not enough evidence.`, fr: `À la taille demandée : ${counts.tension} tension(s), ${counts.nee} preuve(s) insuffisante(s).` })}</>
        )}
      </span>
    </p>
  );
}

function MetricCell({ value, factId, render }: { value: number | null; factId: string | undefined; render: (v: number) => string }) {
  if (value === null) return <span className="muted">—</span>;
  return factId ? <FactChip factId={factId} display={render(value)} /> : <span className="num">{render(value)}</span>;
}

type MetricKey = 'volatilityPct' | 'maxDrawdownPct' | 'stress2022Pct';

export function SnapshotCompare({ before, after }: { before: PortfolioSnapshot; after: PortfolioSnapshot | null }) {
  const { tr, lang } = useApp();
  const rows: { key: MetricKey; label: string; signed: boolean }[] = [
    { key: 'volatilityPct', label: tr({ en: 'Annualized volatility (historical)', fr: 'Volatilité annualisée (historique)' }), signed: false },
    { key: 'maxDrawdownPct', label: tr({ en: 'Maximum drawdown (positive loss)', fr: 'Baisse maximale (perte positive)' }), signed: false },
    { key: 'stress2022Pct', label: tr({ en: '2022 replay return (signed)', fr: 'Rendement rejoué 2022 (signé)' }), signed: true },
  ];
  const tickers = [...new Set([...before.positions.map(p => p.ticker), ...(after?.positions.map(p => p.ticker) ?? [])])];
  const weight = (snapshot: PortfolioSnapshot | null, ticker: string) => snapshot?.positions.find(p => p.ticker === ticker)?.weightPct ?? null;
  const render = (signed: boolean) => (v: number) => (signed ? fmtSignedPct(v, lang) : fmtPct(v, lang));
  return (
    <div className="grid-2">
      <div className="table-scroll" role="region" aria-label={tr({ en: 'Risk before and after', fr: 'Risque avant et après' })} tabIndex={0}>
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">{tr({ en: 'Metric', fr: 'Mesure' })} ({before.currency})</th>
              <th scope="col" className="num-col">{tr({ en: 'Before', fr: 'Avant' })}</th>
              {after && <th scope="col" className="num-col">{tr({ en: 'After (hypothetical)', fr: 'Après (hypothétique)' })}</th>}
            </tr>
          </thead>
          <tbody>
            {rows.map(row => (
              <tr key={row.key}>
                <th scope="row">{row.label}</th>
                <td className="num-col"><MetricCell value={before.metrics[row.key]} factId={factIdFor(before.metrics.factIds, row.key)} render={render(row.signed)} /></td>
                {after && <td className="num-col"><MetricCell value={after.metrics[row.key]} factId={factIdFor(after.metrics.factIds, row.key)} render={render(row.signed)} /></td>}
              </tr>
            ))}
            <tr>
              <th scope="row">{tr({ en: 'Fictional portfolio value', fr: 'Valeur fictive du portefeuille' })}</th>
              <td className="num-col num">{fmtMoney(before.totalValue, before.currency, lang)}</td>
              {after && <td className="num-col num">{fmtMoney(after.totalValue, after.currency, lang)}</td>}
            </tr>
          </tbody>
        </table>
      </div>
      <div className="table-scroll" role="region" aria-label={tr({ en: 'Weights before and after', fr: 'Pondérations avant et après' })} tabIndex={0}>
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">{tr({ en: 'Holding', fr: 'Position' })}</th>
              <th scope="col" className="num-col">{tr({ en: 'Before', fr: 'Avant' })}</th>
              {after && <th scope="col" className="num-col">{tr({ en: 'After', fr: 'Après' })}</th>}
            </tr>
          </thead>
          <tbody>
            {tickers.map(ticker => {
              const b = weight(before, ticker);
              const a = weight(after, ticker);
              const changed = a !== null && b !== null ? Math.abs(a - b) > 0.05 : a !== b;
              return (
                <tr key={ticker}>
                  <th scope="row" className="mono">{ticker}</th>
                  <td className="num-col num">{b === null ? '—' : fmtPct(b, lang)}</td>
                  {after && <td className={`num-col num${changed ? ' changed' : ''}`}>{a === null ? '—' : fmtPct(a, lang)}</td>}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function GroupBars({ items, label, render }: {
  items: readonly { key: string; weightPct: number }[]; label: string; render?: (key: string) => string;
}) {
  const { lang } = useApp();
  return (
    <ul className="bars" aria-label={label}>
      {items.map(item => (
        <li key={item.key} className="bar-row">
          <span className="bar-label">{render ? render(item.key) : labelOf(ASSET_GROUP, item.key, lang)}</span>
          <span className="bar-track" aria-hidden="true"><span className="bar-fill" style={{ width: `${Math.max(0, Math.min(100, item.weightPct))}%` }} /></span>
          <span className="bar-value num">{fmtPct(item.weightPct, lang)}</span>
        </li>
      ))}
    </ul>
  );
}

export function fundingLabel(funding: Funding, lang: Lang): string {
  const base = labelOf(FUNDING_MODE, funding.mode, lang);
  return funding.fromTickers?.length ? `${base}: ${funding.fromTickers.join(', ')}` : base;
}

export function FundingOptions({ options }: { options: readonly FundingOption[] }) {
  const { tr, lang } = useApp();
  if (options.length === 0) return null;
  return (
    <div>
      <h3 className="h4">{tr({ en: 'Hypothetical funding comparison', fr: 'Comparaison hypothétique du financement' })}</h3>
      <div className="table-scroll" role="region" aria-label={tr({ en: 'Funding comparison', fr: 'Comparaison du financement' })} tabIndex={0}>
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">{tr({ en: 'Funding', fr: 'Financement' })}</th>
              <th scope="col">{tr({ en: 'Verdict', fr: 'Verdict' })}</th>
              <th scope="col" className="num-col">{tr({ en: 'Boundary', fr: 'Limite' })}</th>
              <th scope="col">{tr({ en: 'Note', fr: 'Note' })}</th>
            </tr>
          </thead>
          <tbody>
            {[...options].sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99)).map((option, i) => (
              <tr key={`${option.funding.mode}-${i}`}>
                <th scope="row">
                  {fundingLabel(option.funding, lang)}
                  {option.recommended && <span className="tag tag-strong">{tr({ en: 'best fit in this comparison', fr: 'meilleur ajustement dans cette comparaison' })}</span>}
                </th>
                <td>
                  {option.feasible && option.verdict ? <VerdictBadge verdict={option.verdict} />
                    : <span className="muted">{tr({ en: 'Not feasible', fr: 'Irréalisable' })}{option.infeasibleReason ? `: ${tr(option.infeasibleReason)}` : ''}</span>}
                </td>
                <td className="num-col num">{option.maxCompatibleSizePct === null ? '—' : fmtPts(option.maxCompatibleSizePct, lang)}</td>
                <td className="small">{tr(option.note)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function ScenarioCards({ scenarios, selectedId }: { scenarios: readonly Scenario[]; selectedId: string }) {
  const { tr, lang } = useApp();
  if (scenarios.length === 0) {
    return <p className="muted">{tr({ en: 'No supported scenario was found. This is a valid outcome.', fr: 'Aucun scénario étayé n’a été trouvé. C’est un résultat valable.' })}</p>;
  }
  return (
    <div className="scenarios">
      {[...scenarios].sort((a, b) => a.rank - b.rank).map(scenario => (
        <article key={scenario.scenarioId} className={`scenario${scenario.scenarioId === selectedId ? ' selected' : ''}`}
          aria-label={tr(scenario.label)}>
          <p className="eyebrow">{labelOf(SCENARIO_KIND, scenario.kind, lang)}</p>
          <h3 className="h4">{tr(scenario.label)}</h3>
          <div className="tags">
            {scenario.scenarioId === selectedId && <span className="tag tag-strong">{tr({ en: 'selected scenario', fr: 'scénario sélectionné' })}</span>}
            {scenario.isBestFit && scenario.scenarioId !== selectedId && <span className="tag">{tr({ en: 'best-fit alternative', fr: 'meilleure solution de rechange' })}</span>}
          </div>
          <VerdictHeader verdict={scenario.verdict} counts={scenario.counts} />
          {scenario.moves.length > 0 && (
            <ul className="small">
              {scenario.moves.map((move, i) => (
                <li key={`${move.ticker}-${i}`}>
                  <span className="ticker">{move.ticker}</span> +{fmtPts(move.sizePct, lang)}, {fundingLabel(move.funding, lang)}
                </li>
              ))}
            </ul>
          )}
          {scenario.exposure.length > 0 && (
            <ul className="small">
              {scenario.exposure.map(e => <li key={e.theme}>{e.theme}: {fmtPct(e.beforePct, lang)} → {fmtPct(e.afterPct, lang)}</li>)}
            </ul>
          )}
          <p className="small">{tr(scenario.rationale)}</p>
          {scenario.keyFactIds.length > 0 && (
            <p className="small">{tr({ en: 'Key facts', fr: 'Faits clés' })}: {scenario.keyFactIds.map(id => <FactChip key={id} factId={id} />)}</p>
          )}
          <details>
            <summary className="small">{tr({ en: 'Rule checks for this scenario', fr: 'Vérifications pour ce scénario' })}</summary>
            <RuleTable checks={scenario.ruleChecks} caption={tr(scenario.label)} />
          </details>
        </article>
      ))}
    </div>
  );
}
