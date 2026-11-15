'use client';
/**
 * Scope bar: what every Home widget shows. Period (an app window, or a custom date range that the
 * API recomputes every window-based figure on), benchmark (requested from the API), asset classes
 * and minimum weight (narrow the holdings widgets) and how the history chart is drawn.
 */
import { ChevronsUpDown, RotateCcw } from 'lucide-react';
import { useEffect, useState } from 'react';
import type { AssetGroup, I18NText, Lang, WindowCode } from '../../contracts/types';
import { ASSET_GROUP, WINDOW, labelOf } from '../../lib/labels';
import { fmtDate } from '../../lib/format';
import { windowShortLabel } from '../../lib/ui/segmented';
import {
  ASSET_GROUPS, DEFAULT_SCOPE, MIN_WEIGHT_STEPS, isScopeDefault, validateRange, type ChartMode, type DashboardScope,
} from '../../lib/ui/scope';
import { Listbox, type ListboxOption } from '../../components/ui/Listbox';
import { SegmentedControl } from '../../components/ui/SegmentedControl';
import { WINDOW_CODES } from '../../state/app';

type PeriodChoice = WindowCode | 'range';

/** Default custom range: the three years up to the data date. */
function threeYearsBefore(iso: string): string {
  const year = Number(iso.slice(0, 4)) - 3;
  return `${year}${iso.slice(4)}`;
}

const RANGE_ERROR: Record<'format' | 'order' | 'after_data', I18NText> = {
  format: { en: 'Enter two complete dates.', fr: 'Saisissez deux dates complètes.' },
  order: { en: 'The start must be before the end.', fr: 'Le début doit précéder la fin.' },
  after_data: { en: 'The end is after the latest data date.', fr: 'La fin dépasse la dernière date de données.' },
};

export function periodLabel(scope: DashboardScope, windowCode: WindowCode, lang: Lang): string {
  return scope.period.mode === 'custom'
    ? `${fmtDate(scope.period.start, lang)} – ${fmtDate(scope.period.end, lang)}`
    : labelOf(WINDOW, windowCode, lang);
}

export function ScopeBar({ scope, setScope, windowCode, setWindow, dataAsOf, groups, benchmarks, tr, lang }: {
  scope: DashboardScope;
  setScope: (update: (scope: DashboardScope) => DashboardScope) => void;
  windowCode: WindowCode;
  setWindow: (code: WindowCode) => void;
  dataAsOf: string;
  groups: readonly AssetGroup[];
  benchmarks: readonly ListboxOption<string>[];
  tr: (text: I18NText) => string;
  lang: Lang;
}) {
  const custom = scope.period.mode === 'custom' ? scope.period : null;
  const [draft, setDraft] = useState({ start: custom?.start ?? threeYearsBefore(dataAsOf), end: custom?.end ?? dataAsOf });
  useEffect(() => { if (custom) setDraft({ start: custom.start, end: custom.end }); }, [custom?.start, custom?.end]); // eslint-disable-line react-hooks/exhaustive-deps
  const rangeError = custom ? validateRange(draft.start, draft.end, dataAsOf) : null;

  const choosePeriod = (choice: PeriodChoice) => {
    if (choice === 'range') {
      const start = draft.start || threeYearsBefore(dataAsOf);
      const end = draft.end || dataAsOf;
      setScope(s => ({ ...s, period: validateRange(start, end, dataAsOf) ? { mode: 'custom', start: threeYearsBefore(dataAsOf), end: dataAsOf } : { mode: 'custom', start, end } }));
      return;
    }
    setWindow(choice);
    setScope(s => ({ ...s, period: { mode: 'window' } }));
  };
  // A date field reports intermediate years while typing (0002, 0020, 0202…): commit on blur or Enter only.
  const commitRange = () => {
    if (!validateRange(draft.start, draft.end, dataAsOf) && (draft.start !== custom?.start || draft.end !== custom?.end)) {
      setScope(s => ({ ...s, period: { mode: 'custom', start: draft.start, end: draft.end } }));
    }
  };
  const onRangeKey = (event: { key: string }) => { if (event.key === 'Enter') commitRange(); };
  const toggleGroup = (group: AssetGroup) => setScope(s => ({
    ...s,
    assetGroups: s.assetGroups.includes(group) ? s.assetGroups.filter(g => g !== group) : ASSET_GROUPS.filter(g => g === group || s.assetGroups.includes(g)),
  }));

  const periodOptions = [
    ...WINDOW_CODES.map(code => ({ value: code as PeriodChoice, label: windowShortLabel(code, lang), title: labelOf(WINDOW, code, lang) })),
    { value: 'range' as PeriodChoice, label: tr({ en: 'Range', fr: 'Plage' }), title: tr({ en: 'Custom date range', fr: 'Plage de dates personnalisée' }) },
  ];
  const weightOptions: ListboxOption<string>[] = MIN_WEIGHT_STEPS.map(step => ({
    value: String(step),
    label: step === 0 ? tr({ en: 'All positions', fr: 'Toutes les positions' }) : `≥ ${step} %`,
  }));
  const benchmarkOptions: ListboxOption<string>[] = [{ value: '', label: tr({ en: 'None', fr: 'Aucun' }) }, ...benchmarks];
  const chartOptions: { value: ChartMode; label: string; title: string }[] = [
    { value: 'value', label: tr({ en: 'Value', fr: 'Valeur' }), title: tr({ en: 'Fictional value in the reporting currency', fr: 'Valeur fictive dans la devise de référence' }) },
    { value: 'indexed', label: tr({ en: 'Base 100', fr: 'Base 100' }), title: tr({ en: 'Rebased to 100 at the start of the period', fr: 'Rebasé à 100 au début de la période' }) },
    { value: 'drawdown', label: tr({ en: 'Drawdown', fr: 'Repli' }), title: tr({ en: 'Fall from the running peak', fr: 'Baisse depuis le plus haut atteint' }) },
  ];

  return (
    <>
      <div className="scope-bar" role="group" aria-label={tr({ en: 'Dashboard scope', fr: 'Périmètre du tableau de bord' })}>
        <div className="scope-field">
          <span className="scope-label" aria-hidden="true">{tr({ en: 'Period', fr: 'Période' })}</span>
          <SegmentedControl<PeriodChoice> size="sm" label={tr({ en: 'Period', fr: 'Période' })}
            value={custom ? 'range' : windowCode} onChange={choosePeriod} options={periodOptions} />
        </div>
        {custom && (
          <div className="scope-field">
            <span className="scope-label" id="scope-range-label">{tr({ en: 'From – to', fr: 'Du – au' })}</span>
            <div className="scope-range" role="group" aria-labelledby="scope-range-label">
              <input type="date" aria-label={tr({ en: 'Start date', fr: 'Date de début' })} value={draft.start} max={dataAsOf}
                onChange={e => setDraft(d => ({ ...d, start: e.target.value }))} onBlur={commitRange} onKeyDown={onRangeKey}
                aria-invalid={rangeError ? true : undefined} {...(rangeError ? { 'aria-describedby': 'scope-range-error' } : {})} />
              <span className="scope-range-sep" aria-hidden="true">–</span>
              <input type="date" aria-label={tr({ en: 'End date', fr: 'Date de fin' })} value={draft.end} max={dataAsOf}
                onChange={e => setDraft(d => ({ ...d, end: e.target.value }))} onBlur={commitRange} onKeyDown={onRangeKey}
                aria-invalid={rangeError ? true : undefined} {...(rangeError ? { 'aria-describedby': 'scope-range-error' } : {})} />
            </div>
            {rangeError && <span className="scope-error" id="scope-range-error" role="alert">{tr(RANGE_ERROR[rangeError])}</span>}
          </div>
        )}
        <div className="scope-field">
          <span className="scope-label" aria-hidden="true">{tr({ en: 'Benchmark', fr: 'Indice de comparaison' })}</span>
          <Listbox label={tr({ en: 'Benchmark', fr: 'Indice de comparaison' })} value={scope.benchmark ?? ''} options={benchmarkOptions}
            onChange={v => setScope(s => ({ ...s, benchmark: v || null }))} triggerClassName="scope-trigger"
            renderTrigger={() => (<>{scope.benchmark ?? tr({ en: 'None', fr: 'Aucun' })}<ChevronsUpDown className="chev" aria-hidden="true" size={14} strokeWidth={1.5} /></>)} />
        </div>
        <div className="scope-field">
          <span className="scope-label" id="scope-groups-label">{tr({ en: 'Asset classes', fr: 'Classes d’actifs' })}</span>
          <div className="scope-groups" role="group" aria-labelledby="scope-groups-label">
            {groups.map(group => (
              <button key={group} type="button" className="scope-toggle" aria-pressed={scope.assetGroups.includes(group)}
                onClick={() => toggleGroup(group)}>{labelOf(ASSET_GROUP, group, lang)}</button>
            ))}
          </div>
        </div>
        <div className="scope-field">
          <span className="scope-label" aria-hidden="true">{tr({ en: 'Positions', fr: 'Positions' })}</span>
          <Listbox label={tr({ en: 'Minimum weight', fr: 'Poids minimum' })} value={String(scope.minWeight)} options={weightOptions}
            onChange={v => setScope(s => ({ ...s, minWeight: Number(v) }))} triggerClassName="scope-trigger"
            renderTrigger={selected => (<>{selected?.label}<ChevronsUpDown className="chev" aria-hidden="true" size={14} strokeWidth={1.5} /></>)} />
        </div>
        <div className="scope-field">
          <span className="scope-label" aria-hidden="true">{tr({ en: 'Chart', fr: 'Graphique' })}</span>
          <SegmentedControl<ChartMode> size="sm" label={tr({ en: 'History chart view', fr: 'Vue du graphique historique' })}
            value={scope.chartMode} onChange={mode => setScope(s => ({ ...s, chartMode: mode }))} options={chartOptions} />
        </div>
        {!isScopeDefault(scope) && (
          <button type="button" className="btn ghost btn-sm scope-reset" onClick={() => setScope(() => DEFAULT_SCOPE)}>
            <RotateCcw aria-hidden="true" size={14} strokeWidth={1.5} />{tr({ en: 'Reset scope', fr: 'Réinitialiser' })}
          </button>
        )}
      </div>
      <p className="scope-note">
        {tr({ en: 'The period recomputes every window-based figure (volatility, drawdown, worst 12 months, rule checks, history); year-to-date, 1-, 3- and 5-year returns and the 2022 replay are fixed horizons. The benchmark applies to History. Asset classes narrow Allocation and Positions; the minimum weight narrows Positions. Risk and return figures always cover the whole portfolio.', fr: 'La période recalcule chaque chiffre lié à la fenêtre (volatilité, baisse maximale, pires 12 mois, vérifications de règles, historique) ; les rendements depuis janvier, sur 1, 3 et 5 ans et le rejeu 2022 sont à horizon fixe. L’indice s’applique à l’Historique. Les classes d’actifs filtrent Répartition et Positions ; le poids minimum filtre Positions. Les chiffres de risque et de rendement couvrent toujours tout le portefeuille.' })}
      </p>
    </>
  );
}
