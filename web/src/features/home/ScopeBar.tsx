'use client';
/**
 * Scope bar: what the Home widgets show. Period (an app window, or a custom date range that the
 * API recomputes every window-based figure on), benchmark (a comparison line on Past performance),
 * asset classes (Allocation and Positions) and minimum weight (Positions only), and how the history
 * chart is drawn. A scope that differs from the default is named in a badge above the bar, with Reset;
 * the scope is saved in this browser (aplomb.pref.dashboard.scope.v1). On phones only the period
 * stays visible; the other filters sit in a "Filters" disclosure that starts closed on every load.
 */
import { ChevronsUpDown, RotateCcw, SlidersHorizontal } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import type { AssetGroup, I18NText, Lang, WindowCode } from '../../contracts/types';
import { ASSET_GROUP, WINDOW, labelOf } from '../../lib/labels';
import { fmtDate } from '../../lib/format';
import { windowShortLabel } from '../../lib/ui/segmented';
import {
  ASSET_GROUPS, DEFAULT_SCOPE, MIN_WEIGHT_STEPS, defaultRange, hiddenFilterCount, isScopeDefault, scopeSummary, validateRange,
  type ChartMode, type DashboardScope,
} from '../../lib/ui/scope';
import { Listbox, type ListboxOption } from '../../components/ui/Listbox';
import { SegmentedControl } from '../../components/ui/SegmentedControl';
import { InfoTip } from '../../components/ui/InfoTip';
import { WINDOW_CODES } from '../../state/app';

type PeriodChoice = WindowCode | 'range';

const RANGE_ERROR: Record<'format' | 'order' | 'after_data', I18NText> = {
  format: { en: 'Enter two complete dates.', fr: 'Saisissez deux dates complètes.' },
  order: { en: 'The start must be before the end.', fr: 'Le début doit précéder la fin.' },
  after_data: { en: 'The end is after the latest data date.', fr: 'La fin dépasse la dernière date de données.' },
};

/** What each scope control changes (checked against HomePage: only the period reaches the overview). */
const SCOPE_EFFECTS: I18NText = {
  en: 'Period recomputes the return, volatility, drawdown, lowest rolling 12-month return, rule checks and Past performance. Benchmark adds a comparison line to Past performance. Asset classes filter Allocation and Positions; minimum weight filters Positions only. The 3- and 5-year totals and the 2022 replay are fixed horizons. The portfolio brief always covers the whole portfolio and the app window.',
  fr: 'La période recalcule le rendement, la volatilité, la baisse maximale, le plus faible rendement glissant sur 12 mois, les vérifications de règles et la Performance passée. L’indice ajoute une courbe de comparaison à la Performance passée. Les classes d’actifs filtrent Répartition et Positions ; le poids minimum ne filtre que Positions. Les totaux sur 3 et 5 ans et le rejeu 2022 sont à horizon fixe. La note de portefeuille couvre toujours tout le portefeuille et la fenêtre de l’application.',
};

export function periodLabel(scope: DashboardScope, windowCode: WindowCode, lang: Lang): string {
  return scope.period.mode === 'custom'
    ? `${fmtDate(scope.period.start, lang)} – ${fmtDate(scope.period.end, lang)}`
    : labelOf(WINDOW, windowCode, lang);
}

export function ScopeBar({ scope, setScope, windowCode, setWindow, dataAsOf, shownPeriod, groups, benchmarks, tr, lang, announce }: {
  scope: DashboardScope;
  setScope: (update: (scope: DashboardScope) => DashboardScope) => void;
  windowCode: WindowCode;
  setWindow: (code: WindowCode) => void;
  dataAsOf: string;
  /** First and last day the API resolved for the window on screen (null until the overview loads). */
  shownPeriod: { start: string; end: string } | null;
  groups: readonly AssetGroup[];
  benchmarks: readonly ListboxOption<string>[];
  tr: (text: I18NText) => string;
  lang: Lang;
  announce: (message: string) => void;
}) {
  const custom = scope.period.mode === 'custom' ? scope.period : null;
  const [draft, setDraft] = useState(() => (custom ? { start: custom.start, end: custom.end } : defaultRange(windowCode, dataAsOf, shownPeriod)));
  useEffect(() => { if (custom) setDraft({ start: custom.start, end: custom.end }); }, [custom?.start, custom?.end]); // eslint-disable-line react-hooks/exhaustive-deps
  const rangeError = custom ? validateRange(draft.start, draft.end, dataAsOf) : null;
  // Phones: the filters other than the period start hidden on every load (not stored).
  const [filtersOpen, setFiltersOpen] = useState(false);
  const bar = useRef<HTMLDivElement | null>(null);

  const choosePeriod = (choice: PeriodChoice) => {
    if (choice === 'range') {
      if (custom) return; // already a range: keep the dates the person chose
      // Start from the period on screen, so switching to Range alone changes no figure.
      const next = defaultRange(windowCode, dataAsOf, shownPeriod);
      setDraft(next);
      setScope(s => ({ ...s, period: { mode: 'custom', ...next } }));
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
  const reset = () => {
    setScope(() => DEFAULT_SCOPE);
    announce(tr({ en: 'Dashboard scope reset', fr: 'Périmètre du tableau de bord réinitialisé' }));
    // The Reset button disappears with the badge: keep focus in the scope bar, on the chosen period.
    requestAnimationFrame(() => bar.current?.querySelector<HTMLElement>('[role="radio"][aria-checked="true"]')?.focus());
  };

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
  const summary = scopeSummary(scope, lang);
  const hidden = hiddenFilterCount(scope);

  return (
    <>
      {!isScopeDefault(scope) && (
        <div className="scope-summary">
          <span>{tr({ en: 'Custom scope:', fr: 'Périmètre personnalisé :' })} {summary.join(', ')}</span>
          <span aria-hidden="true">·</span>
          <button type="button" className="btn ghost btn-sm" onClick={reset}
            aria-label={tr({ en: 'Reset the dashboard scope', fr: 'Réinitialiser le périmètre du tableau de bord' })}>
            <RotateCcw aria-hidden="true" size={14} strokeWidth={1.5} />{tr({ en: 'Reset', fr: 'Réinitialiser' })}
          </button>
          <span className="scope-saved">{tr({ en: 'Saved in this browser.', fr: 'Enregistré dans ce navigateur.' })}</span>
        </div>
      )}
      <div ref={bar} className="scope-bar" role="group" aria-label={tr({ en: 'Dashboard scope', fr: 'Périmètre du tableau de bord' })} data-tour="scope">
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
        {/* Shown below 768 px only (CSS); its visible text is its accessible name. */}
        <button type="button" className="scope-trigger scope-filters-toggle" aria-expanded={filtersOpen} aria-controls="scope-filters"
          onClick={() => setFiltersOpen(open => !open)}>
          <SlidersHorizontal aria-hidden="true" size={14} strokeWidth={1.5} />
          {hidden > 0 ? tr({ en: `Filters · ${hidden}`, fr: `Filtres · ${hidden}` }) : tr({ en: 'Filters', fr: 'Filtres' })}
        </button>
        <div id="scope-filters" className="scope-filters" data-open={filtersOpen ? 'true' : undefined}>
          <div className="scope-field">
            <span className="scope-label" aria-hidden="true">{tr({ en: 'Benchmark', fr: 'Indice de comparaison' })}</span>
            <Listbox label={tr({ en: 'Benchmark', fr: 'Indice de comparaison' })} value={scope.benchmark ?? ''} options={benchmarkOptions}
              onChange={v => setScope(s => ({ ...s, benchmark: v || null }))} triggerClassName="scope-trigger"
              renderTrigger={() => (<>{scope.benchmark ?? tr({ en: 'None', fr: 'Aucun' })}<ChevronsUpDown className="chev" aria-hidden="true" size={14} strokeWidth={1.5} /></>)} />
          </div>
          <div className="scope-field">
            <span className="scope-label" id="scope-groups-label">{tr({ en: 'Asset classes', fr: 'Classes d’actifs' })}</span>
            <div className="scope-groups" role="group" aria-labelledby="scope-groups-label" aria-describedby="scope-groups-hint">
              {groups.map(group => (
                <button key={group} type="button" className="scope-toggle" aria-pressed={scope.assetGroups.includes(group)}
                  onClick={() => toggleGroup(group)}>{labelOf(ASSET_GROUP, group, lang)}</button>
              ))}
            </div>
            <span className="scope-hint" id="scope-groups-hint">{tr({ en: 'Filters Allocation and Positions only', fr: 'Ne filtre que Répartition et Positions' })}</span>
          </div>
          <div className="scope-field">
            <span className="scope-label" aria-hidden="true">{tr({ en: 'Positions', fr: 'Positions' })}</span>
            <Listbox label={tr({ en: 'Minimum weight', fr: 'Poids minimum' })} value={String(scope.minWeight)} options={weightOptions}
              onChange={v => setScope(s => ({ ...s, minWeight: Number(v) }))} triggerClassName="scope-trigger"
              renderTrigger={selected => (<>{selected?.label}<ChevronsUpDown className="chev" aria-hidden="true" size={14} strokeWidth={1.5} /></>)} />
            <span className="scope-hint">{tr({ en: 'Filters Positions only', fr: 'Ne filtre que Positions' })}</span>
          </div>
          <div className="scope-field">
            <span className="scope-label" aria-hidden="true">{tr({ en: 'Chart', fr: 'Graphique' })}</span>
            <SegmentedControl<ChartMode> size="sm" label={tr({ en: 'History chart view', fr: 'Vue du graphique historique' })}
              value={scope.chartMode} onChange={mode => setScope(s => ({ ...s, chartMode: mode }))} options={chartOptions} />
          </div>
        </div>
        <span className="scope-end">
          <InfoTip align="end" label={tr({ en: 'What the scope changes', fr: 'Ce que change le périmètre' })} text={tr(SCOPE_EFFECTS)} />
        </span>
      </div>
    </>
  );
}
