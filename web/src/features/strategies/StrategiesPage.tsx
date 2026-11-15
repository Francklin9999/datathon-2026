'use client';
/**
 * Strategies (api.md §3.13, web/page-specs/strategies.md): the investor saves up to three standing
 * strategies (automations) per profile in this browser, configures them, and sees each one simulated
 * on the history of today's holdings next to the same holdings left untouched. Deterministic, no
 * model; nothing is executed. Every setting change re-simulates (debounced).
 */
import Link from 'next/link';
import { PiggyBank, Plus, RefreshCcw, ShieldHalf, Trash2, type LucideIcon } from 'lucide-react';
import { useEffect, useMemo, useState, type ReactNode } from 'react';
import type { Lang, Profile, StrategyConfig, StrategySimulation, StrategyTrade } from '../../contracts/types';
import { getApiClient } from '../../api/index';
import { profileKey, useApp } from '../../state/app';
import { useQuery } from '../../state/useQuery';
import { Card, PageHeader, ProfileGate } from '../../components/common/Page';
import { ErrorState, Loading } from '../../components/common/States';
import { LimitationList } from '../../components/common/FactDrawer';
import { LineChart, type Series } from '../../components/common/LineChart';
import { Sheet, useSheet } from '../../components/common/Sheet';
import { SegmentedControl } from '../../components/ui/SegmentedControl';
import { CountUp } from '../../components/ui/CountUp';
import { InfoTip } from '../../components/ui/InfoTip';
import { WindowControl } from '../../components/shell/TopBar';
import { readPref, writePref } from '../../lib/session';
import { fillThreshold, fmtDate, fmtMoney, fmtNumber, fmtPct, fmtSignedPct } from '../../lib/format';
import {
  KIND_NAME, KIND_PURPOSE, MAX_STRATEGIES, STRATEGY_KINDS, configIssues, describe, newStrategy, readStrategies, wireConfig, writeStrategies,
  type SavedStrategy, type StrategyKind,
} from '../../lib/strategies';

export const KIND_ICON: Record<StrategyKind, LucideIcon> = { rebalance: RefreshCcw, contribute: PiggyBank, risk_guard: ShieldHalf };

export function StrategiesPage() {
  return <ProfileGate>{profile => <StrategiesContent key={profile.profileId} profile={profile} />}</ProfileGate>;
}

/** Saved strategies of a profile, kept in this browser. */
function useSavedStrategies(profileId: string) {
  const [list, setList] = useState<SavedStrategy[]>([]);
  useEffect(() => { setList(readStrategies(profileId, readPref)); }, [profileId]);
  const save = (next: SavedStrategy[]) => { setList(next); writeStrategies(profileId, next, writePref); };
  return [list, save] as const;
}

/** The simulation of one strategy for the session window (shared with Home's widget through the cache). */
export function useStrategySimulation(profile: Profile, config: StrategyConfig | null) {
  const app = useApp();
  const base = profileKey(app);
  const body = config && configIssues(config).length === 0 ? wireConfig(config) : null;
  const key = base && body ? `strategy|${base}|${app.windowCode}|${JSON.stringify(body)}` : null;
  return useQuery<StrategySimulation>(key, signal => getApiClient().simulateStrategy(profile.profileId, { strategy: body!, window: { code: app.windowCode } }, signal));
}

function StrategiesContent({ profile }: { profile: Profile }) {
  const { tr } = useApp();
  const [list, save] = useSavedStrategies(profile.profileId);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [choosing, setChoosing] = useState(false);
  const selected = list.find(s => s.id === selectedId) ?? list[0] ?? null;
  const full = list.length >= MAX_STRATEGIES;

  const create = (kind: StrategyKind) => {
    const made = newStrategy(kind, list, tr, `st_${Date.now().toString(36)}`);
    save([...list, made]);
    setSelectedId(made.id);
    setChoosing(false);
  };
  const update = (next: SavedStrategy) => save(list.map(s => (s.id === next.id ? next : s)));
  const remove = (id: string) => { save(list.filter(s => s.id !== id)); setSelectedId(null); };

  return (
    <>
      <PageHeader actions={<WindowControl />} tour="strategies-header" title={tr({ en: 'Strategies', fr: 'Stratégies' })}>
        <p className="page-sub">{tr({ en: `Standing rules tested on the history of ${profile.name}’s holdings. Nothing is executed.`, fr: `Des règles permanentes testées sur l’historique des positions de ${profile.name}. Rien n’est exécuté.` })}</p>
      </PageHeader>

      {(list.length === 0 || choosing) ? (
        <KindPicker onPick={create} onCancel={list.length > 0 ? () => setChoosing(false) : undefined} />
      ) : (
        <div className="strategy-layout">
          <aside className="strategy-list" aria-label={tr({ en: 'Your strategies', fr: 'Vos stratégies' })}>
            {list.map(s => {
              const Icon = KIND_ICON[s.config.kind];
              return (
                <button key={s.id} type="button" className="strategy-item" aria-pressed={s.id === selected?.id} onClick={() => setSelectedId(s.id)}>
                  <span className={`strategy-icon kind-${s.config.kind}`} aria-hidden="true"><Icon size={17} strokeWidth={2} /></span>
                  <span className="strategy-item-body">
                    <span className="strategy-item-name">{s.name}</span>
                    <span className="strategy-item-meta">{s.active ? tr({ en: 'Active', fr: 'Active' }) : tr({ en: 'Paused', fr: 'En pause' })}</span>
                  </span>
                </button>
              );
            })}
            <button type="button" className="strategy-add" onClick={() => setChoosing(true)} disabled={full}
              title={full ? tr({ en: `At most ${MAX_STRATEGIES} strategies`, fr: `Au plus ${MAX_STRATEGIES} stratégies` }) : undefined}>
              <Plus aria-hidden="true" size={16} strokeWidth={2} />
              {full ? tr({ en: `${MAX_STRATEGIES} of ${MAX_STRATEGIES}`, fr: `${MAX_STRATEGIES} sur ${MAX_STRATEGIES}` }) : tr({ en: 'New strategy', fr: 'Nouvelle stratégie' })}
            </button>
          </aside>
          {selected && <StrategyWorkspace key={selected.id} profile={profile} strategy={selected} onChange={update} onDelete={() => remove(selected.id)} />}
        </div>
      )}
    </>
  );
}

function KindPicker({ onPick, onCancel }: { onPick: (kind: StrategyKind) => void; onCancel?: (() => void) | undefined }) {
  const { tr } = useApp();
  return (
    <section className="kind-picker" aria-label={tr({ en: 'Choose a strategy', fr: 'Choisir une stratégie' })}>
      <div className="kind-grid">
        {STRATEGY_KINDS.map(kind => {
          const Icon = KIND_ICON[kind];
          return (
            <button key={kind} type="button" className="kind-card" onClick={() => onPick(kind)}>
              <span className={`strategy-icon strategy-icon-lg kind-${kind}`} aria-hidden="true"><Icon size={22} strokeWidth={2} /></span>
              <span className="kind-name">{tr(KIND_NAME[kind])}</span>
              <span className="kind-purpose">{tr(KIND_PURPOSE[kind])}</span>
              <span className="kind-cta"><Plus aria-hidden="true" size={14} strokeWidth={2.25} />{tr({ en: 'Create', fr: 'Créer' })}</span>
            </button>
          );
        })}
      </div>
      {onCancel && <p className="kind-cancel"><button type="button" className="btn ghost btn-sm" onClick={onCancel}>{tr({ en: 'Cancel', fr: 'Annuler' })}</button></p>}
    </section>
  );
}

function StrategyWorkspace({ profile, strategy, onChange, onDelete }: {
  profile: Profile; strategy: SavedStrategy; onChange: (next: SavedStrategy) => void; onDelete: () => void;
}) {
  const { tr, lang } = useApp();
  // Settings apply after a short pause, so typing a number does not run a simulation per key.
  const [committed, setCommitted] = useState(strategy.config);
  useEffect(() => {
    const timer = window.setTimeout(() => setCommitted(strategy.config), 350);
    return () => window.clearTimeout(timer);
  }, [strategy.config]);
  const sim = useStrategySimulation(profile, committed);
  const issues = configIssues(strategy.config);
  const money = (n: number) => fmtMoney(n, profile.reportingCurrency, lang);
  const setConfig = (config: StrategyConfig) => onChange({ ...strategy, config });

  return (
    <div className="strategy-main">
      <Card title={strategy.name} actions={(
        <>
          <label className="switch">
            <input type="checkbox" checked={strategy.active} onChange={e => onChange({ ...strategy, active: e.target.checked })} />
            <span className="switch-track" aria-hidden="true"><span className="switch-thumb" /></span>
            <span className="switch-label">{tr({ en: 'Active on Home', fr: 'Active sur l’accueil' })}</span>
          </label>
          <button type="button" className="icon-btn details-btn" onClick={onDelete}
            aria-label={tr({ en: `Delete ${strategy.name}`, fr: `Supprimer ${strategy.name}` })} title={tr({ en: 'Delete', fr: 'Supprimer' })}>
            <Trash2 aria-hidden="true" size={14} strokeWidth={2} />
          </button>
        </>
      )}>
        <p className="strategy-summary">{describe(strategy.config, tr, money)}</p>
        <div className="strategy-form">
          <Field label={tr({ en: 'Name', fr: 'Nom' })}>
            <input type="text" value={strategy.name} maxLength={60} onChange={e => onChange({ ...strategy, name: e.target.value || tr(KIND_NAME[strategy.config.kind]) })} />
          </Field>
          <ConfigFields config={strategy.config} onChange={setConfig} currency={profile.reportingCurrency} />
        </div>
        {issues.length > 0 && <ul className="field-error strategy-issues" role="alert">{issues.map((m, i) => <li key={i}>{tr(m)}</li>)}</ul>}
      </Card>

      {sim.loading && !sim.data && <Loading label={tr({ en: 'Simulating on history…', fr: 'Simulation sur l’historique…' })} />}
      {sim.error && <ErrorState error={sim.error} onRetry={sim.reload} title={tr({ en: 'The simulation is unavailable for this window.', fr: 'La simulation est indisponible pour cette période.' })} />}
      {sim.data && <Results sim={sim.data} profile={profile} lang={lang} stale={sim.loading} />}
    </div>
  );
}

function Field({ label, info, children }: { label: string; info?: string; children: ReactNode }) {
  return (
    <div className="field">
      <span className="field-label">{label}{info && <InfoTip text={info} align="start" />}</span>
      {children}
    </div>
  );
}

function NumberInput({ value, min, max, step, suffix, onChange, label }: {
  value: number; min: number; max: number; step: number; suffix: string; onChange: (n: number) => void; label: string;
}) {
  return (
    <span className="number-input">
      <input type="number" inputMode="decimal" aria-label={label} value={Number.isFinite(value) ? value : ''} min={min} max={max} step={step}
        onChange={e => onChange(e.target.value === '' ? Number.NaN : Number(e.target.value))} />
      <span className="number-suffix" aria-hidden="true">{suffix}</span>
    </span>
  );
}

function ConfigFields({ config, onChange, currency }: { config: StrategyConfig; onChange: (c: StrategyConfig) => void; currency: string }) {
  const { tr } = useApp();
  const cost = (
    <Field label={tr({ en: 'Cost per trade', fr: 'Frais par opération' })}
      info={tr({ en: 'A flat rate on every traded amount (10 bps = 0.10%). Taxes and spreads are not modelled.', fr: 'Un taux fixe sur chaque montant échangé (10 pb = 0,10 %). Impôts et écarts ne sont pas modélisés.' })}>
      <NumberInput label={tr({ en: 'Cost per trade, basis points', fr: 'Frais par opération, points de base' })} value={config.costBps ?? 0} min={0} max={100} step={1} suffix={tr({ en: 'bps', fr: 'pb' })}
        onChange={n => onChange({ ...config, costBps: n })} />
    </Field>
  );
  const freq = [
    { value: 'monthly' as const, label: tr({ en: 'Monthly', fr: 'Mensuel' }) },
    { value: 'quarterly' as const, label: tr({ en: 'Quarterly', fr: 'Trimestriel' }) },
    { value: 'yearly' as const, label: tr({ en: 'Yearly', fr: 'Annuel' }) },
  ];
  if (config.kind === 'rebalance') {
    return (
      <>
        <Field label={tr({ en: 'When', fr: 'Quand' })}>
          <SegmentedControl<'calendar' | 'band'> size="sm" label={tr({ en: 'Rebalancing trigger', fr: 'Déclencheur du rééquilibrage' })} value={config.trigger}
            onChange={trigger => onChange({ ...config, trigger })}
            options={[{ value: 'calendar', label: tr({ en: 'On a schedule', fr: 'Selon un calendrier' }) }, { value: 'band', label: tr({ en: 'On drift', fr: 'Selon l’écart' }) }]} />
        </Field>
        {config.trigger === 'calendar' ? (
          <Field label={tr({ en: 'Every', fr: 'Chaque' })}>
            <SegmentedControl size="sm" label={tr({ en: 'Rebalancing frequency', fr: 'Fréquence du rééquilibrage' })} value={config.frequency ?? 'quarterly'}
              onChange={frequency => onChange({ ...config, frequency })} options={freq} />
          </Field>
        ) : (
          <Field label={tr({ en: 'Band', fr: 'Bande' })} info={tr({ en: 'Rebalance on a day when a position is this many points from its target weight.', fr: 'Rééquilibrer le jour où une position s’écarte de ce nombre de points de sa pondération cible.' })}>
            <NumberInput label={tr({ en: 'Drift band, points', fr: 'Bande d’écart, points' })} value={config.bandPts ?? 5} min={1} max={25} step={0.5} suffix="pts"
              onChange={n => onChange({ ...config, bandPts: n })} />
          </Field>
        )}
        {cost}
      </>
    );
  }
  if (config.kind === 'contribute') {
    return (
      <>
        <Field label={tr({ en: 'Amount', fr: 'Montant' })}>
          <NumberInput label={tr({ en: `Amount per period, ${currency}`, fr: `Montant par période, ${currency}` })} value={config.amount} min={1} max={1_000_000} step={100} suffix={currency}
            onChange={amount => onChange({ ...config, amount })} />
        </Field>
        <Field label={tr({ en: 'Every', fr: 'Chaque' })}>
          <SegmentedControl size="sm" label={tr({ en: 'Contribution frequency', fr: 'Fréquence des versements' })} value={config.frequency}
            onChange={frequency => onChange({ ...config, frequency })} options={freq.slice(0, 2) as { value: 'monthly' | 'quarterly'; label: string }[]} />
        </Field>
        <Field label={tr({ en: 'Invest in', fr: 'Investir dans' })}>
          <SegmentedControl<'underweight' | 'target'> size="sm" label={tr({ en: 'Where contributions go', fr: 'Où vont les versements' })} value={config.allocation}
            onChange={allocation => onChange({ ...config, allocation })}
            options={[{ value: 'underweight', label: tr({ en: 'Most underweight', fr: 'Les plus en retard' }) }, { value: 'target', label: tr({ en: 'Target weights', fr: 'Selon les cibles' }) }]} />
        </Field>
        {cost}
      </>
    );
  }
  return (
    <>
      <Field label={tr({ en: 'Trigger', fr: 'Seuil' })} info={tr({ en: 'Fall from the strategy’s own peak value that starts the protection.', fr: 'Baisse depuis la valeur la plus haute atteinte qui déclenche la protection.' })}>
        <NumberInput label={tr({ en: 'Trigger, fall from the peak in percent', fr: 'Seuil, baisse depuis le sommet en pour cent' })} value={config.triggerDrawdownPct} min={2} max={50} step={1} suffix="%"
          onChange={n => onChange({ ...config, triggerDrawdownPct: n })} />
      </Field>
      <Field label={tr({ en: 'Move to safety', fr: 'Mettre à l’abri' })} info={tr({ en: 'Share of each stock and crypto position moved to the defensive asset (the largest bond fund held, else cash).', fr: 'Part de chaque position en actions et en crypto déplacée vers l’actif défensif (le plus gros fonds obligataire détenu, sinon l’encaisse).' })}>
        <NumberInput label={tr({ en: 'Share moved, percent', fr: 'Part déplacée, pour cent' })} value={config.shiftPct} min={10} max={100} step={5} suffix="%"
          onChange={n => onChange({ ...config, shiftPct: n })} />
      </Field>
      <Field label={tr({ en: 'Return under', fr: 'Revenir sous' })} info={tr({ en: 'Target weights come back once the fall from the peak is under this level.', fr: 'Les pondérations cibles reviennent une fois la baisse depuis le sommet sous ce niveau.' })}>
        <NumberInput label={tr({ en: 'Return level, fall from the peak in percent', fr: 'Niveau de retour, baisse depuis le sommet en pour cent' })} value={config.reentryDrawdownPct} min={0} max={49} step={1} suffix="%"
          onChange={n => onChange({ ...config, reentryDrawdownPct: n })} />
      </Field>
      {cost}
    </>
  );
}

const ACTION_KIND: Record<StrategySimulation['actions'][number]['kind'], { en: string; fr: string }> = {
  rebalance: { en: 'Rebalance', fr: 'Rééquilibrage' },
  contribute: { en: 'Contribution', fr: 'Versement' },
  de_risk: { en: 'Protection', fr: 'Protection' },
  re_risk: { en: 'Back to target', fr: 'Retour aux cibles' },
};

function Results({ sim, profile, lang, stale }: { sim: StrategySimulation; profile: Profile; lang: Lang; stale: boolean }) {
  const { tr } = useApp();
  const m = sim.metrics;
  const b = sim.baselineMetrics;
  const money = (n: number) => fmtMoney(n, sim.currency, lang);
  const contribute = sim.strategy.kind === 'contribute';
  const series: Series[] = [
    { label: tr({ en: 'With the strategy', fr: 'Avec la stratégie' }), points: sim.series, color: 'var(--chart-1)' },
    { label: tr({ en: 'Untouched', fr: 'Sans y toucher' }), points: sim.baseline, color: 'var(--chart-4)', dashed: true },
  ];
  if (sim.invested) series.push({ label: tr({ en: 'Invested', fr: 'Investi' }), points: sim.invested, color: 'var(--cat-3)', dashed: true });
  const caption = `${fmtDate(sim.series[0]?.date ?? '', lang)} → ${fmtDate(sim.series[sim.series.length - 1]?.date ?? '', lang)}`;
  const ruleLabel = (ruleId: string, code: string) => {
    const rule = profile.rules.find(r => r.ruleId === ruleId);
    return rule ? `${code} · ${fillThreshold(tr(rule.label), rule.threshold, rule.unit, lang)}` : code;
  };
  const delta = (a: number | null, z: number | null, fmt: (n: number) => string) => (a === null || z === null ? null : fmt(a - z));
  return (
    <div className="strategy-results" aria-busy={stale}>
      <div className="strategy-kpis">
        <Kpi label={contribute ? tr({ en: 'Gain on invested', fr: 'Gain sur investi' }) : tr({ en: 'Ending value', fr: 'Valeur finale' })}
          value={contribute ? money(m.gain) : money(m.endValue)}
          compare={contribute
            ? tr({ en: `${money(m.invested)} invested`, fr: `${money(m.invested)} investis` })
            : tr({ en: `${money(b.endValue)} untouched`, fr: `${money(b.endValue)} sans y toucher` })} />
        <Kpi label={tr({ en: 'Return', fr: 'Rendement' })} value={fmtSignedPct(m.twrPct, lang)}
          compare={tr({ en: `${fmtSignedPct(b.twrPct, lang)} untouched`, fr: `${fmtSignedPct(b.twrPct, lang)} sans y toucher` })}
          info={tr({ en: 'Time-weighted: contributions are removed, so it compares with the untouched holdings.', fr: 'Pondéré dans le temps : les versements sont retirés, donc comparable aux positions laissées telles quelles.' })} />
        <Kpi label={tr({ en: 'Deepest fall', fr: 'Pire baisse' })} value={m.maxDrawdownPct === null ? '—' : fmtPct(m.maxDrawdownPct, lang)}
          compare={b.maxDrawdownPct === null ? '' : tr({ en: `${fmtPct(b.maxDrawdownPct, lang)} untouched`, fr: `${fmtPct(b.maxDrawdownPct, lang)} sans y toucher` })}
          tone={m.maxDrawdownPct !== null && b.maxDrawdownPct !== null ? (m.maxDrawdownPct < b.maxDrawdownPct - 0.05 ? 'good' : m.maxDrawdownPct > b.maxDrawdownPct + 0.05 ? 'bad' : undefined) : undefined}
          hint={delta(m.maxDrawdownPct, b.maxDrawdownPct, n => `${n > 0 ? '+' : ''}${fmtNumber(n, lang, 1)} pts`)} />
        <Kpi label={tr({ en: 'Months outside the plan', fr: 'Mois hors du plan' })} value={String(sim.plan.strategyMonthsInConflict)}
          compare={tr({ en: `${sim.plan.baselineMonthsInConflict} untouched, of ${sim.plan.monthsChecked}`, fr: `${sim.plan.baselineMonthsInConflict} sans y toucher, sur ${sim.plan.monthsChecked}` })}
          tone={sim.plan.strategyMonthsInConflict < sim.plan.baselineMonthsInConflict ? 'good' : sim.plan.strategyMonthsInConflict > sim.plan.baselineMonthsInConflict ? 'bad' : undefined}
          info={tr({ en: 'Month ends when the holdings broke an allocation rule of the plan (caps and floors).', fr: 'Fins de mois où les positions enfreignaient une règle de répartition du plan (plafonds et planchers).' })} />
      </div>

      <div className="strategy-row">
        <Card title={tr({ en: 'With and without', fr: 'Avec et sans' })} className="strategy-chart">
          <LineChart series={series} lang={lang} unitLabel={sim.currency} caption={caption} />
        </Card>
        <NextAction sim={sim} money={money} />
      </div>

      <div className="strategy-row">
        <Activity sim={sim} money={money} />
        <Card title={tr({ en: 'Plan check', fr: 'Vérification du plan' })} className="strategy-plan">
          <p className="figure-note">{tr({ en: `${m.actions} actions, ${fmtNumber(m.turnoverPct, lang, 0)}% turnover, ${money(m.costs)} of costs.`, fr: `${m.actions} actions, ${fmtNumber(m.turnoverPct, lang, 0)} % de rotation, ${money(m.costs)} de frais.` })}</p>
          {sim.plan.byRule.length === 0
            ? <p className="small muted">{tr({ en: 'No allocation rule was broken at a month end, with or without the strategy.', fr: 'Aucune règle de répartition enfreinte en fin de mois, avec ou sans la stratégie.' })}</p>
            : (
              <ul className="plan-rows">
                {sim.plan.byRule.map(row => (
                  <li key={row.ruleId}>
                    <span className="plan-rule">{ruleLabel(row.ruleId, row.code)}</span>
                    <span className="plan-months"><strong>{row.strategyMonths}</strong> <span className="muted">/ {row.baselineMonths}</span></span>
                  </li>
                ))}
              </ul>
            )}
          {sim.plan.byRule.length > 0 && <p className="small muted plan-legend">{tr({ en: 'Months in conflict: with the strategy / untouched', fr: 'Mois en conflit : avec la stratégie / sans y toucher' })}</p>}
        </Card>
      </div>

      <LimitationList compactAfter={0} codes={sim.limitations} />
      <p className="small muted">
        <Link href="/decision-desk/">{tr({ en: 'Test a single move instead', fr: 'Tester plutôt un mouvement ponctuel' })}</Link>
      </p>
    </div>
  );
}

function Kpi({ label, value, compare, info, tone, hint }: { label: string; value: string; compare: string; info?: string; tone?: 'good' | 'bad' | undefined; hint?: string | null }) {
  return (
    <div className="strategy-kpi" {...(tone ? { 'data-tone': tone } : {})}>
      <span className="kpi-label">{label}{info && <InfoTip text={info} align="start" />}</span>
      <span className="strategy-kpi-value"><CountUp text={value} /></span>
      <span className="kpi-note">{compare}{hint ? ` · ${hint}` : ''}</span>
    </div>
  );
}

function TradeRows({ trades, money }: { trades: readonly StrategyTrade[]; money: (n: number) => string }) {
  const { tr, lang } = useApp();
  return (
    <table className="rank-table trade-table">
      <caption className="sr-only">{tr({ en: 'Trades', fr: 'Opérations' })}</caption>
      <thead>
        <tr>
          <th scope="col">{tr({ en: 'Asset', fr: 'Actif' })}</th>
          <th scope="col" className="num-col">{tr({ en: 'Amount', fr: 'Montant' })}</th>
          <th scope="col" className="num-col">{tr({ en: 'Weight', fr: 'Poids' })}</th>
        </tr>
      </thead>
      <tbody>
        {[...trades].sort((x, y) => Math.abs(y.amount) - Math.abs(x.amount)).map(t => (
          <tr key={t.ticker}>
            <th scope="row" className="rank-ticker">{t.ticker}</th>
            <td className={`num-col ${t.amount >= 0 ? 'trade-buy' : 'trade-sell'}`}>{t.amount >= 0 ? '+' : '−'}{money(Math.abs(t.amount))}</td>
            <td className="num-col">{fmtPct(t.weightBeforePct, lang)} → {fmtPct(t.weightAfterPct, lang)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function NextAction({ sim, money }: { sim: StrategySimulation; money: (n: number) => string }) {
  const { tr } = useApp();
  const next = sim.nextAction;
  return (
    <Card title={tr({ en: 'Next action', fr: 'Prochaine action' })} className="strategy-next">
      <p className="next-state" data-due={next.due ? 'true' : undefined}>
        <span className="next-dot" aria-hidden="true" />
        {next.due ? tr({ en: 'Due now', fr: 'À faire maintenant' }) : tr({ en: 'Nothing due', fr: 'Rien à faire' })}
      </p>
      <p className="next-summary">{tr(next.summary)}</p>
      {next.trades.length > 0 && <TradeRows trades={next.trades.slice(0, 6)} money={money} />}
      <p className="small muted">{tr({ en: 'Proposed only: no order is placed.', fr: 'Proposé seulement : aucun ordre n’est passé.' })}</p>
    </Card>
  );
}

function Activity({ sim, money }: { sim: StrategySimulation; money: (n: number) => string }) {
  const { tr, lang } = useApp();
  const sheet = useSheet();
  const latest = useMemo(() => [...sim.actions].reverse(), [sim.actions]);
  const row = (a: StrategySimulation['actions'][number], open: boolean) => (
    <li key={`${a.date}-${a.kind}`} className="activity-item">
      <span className={`activity-kind kind-${a.kind}`}>{tr(ACTION_KIND[a.kind])}</span>
      <span className="activity-date">{fmtDate(a.date, lang)}</span>
      <span className="activity-reason">{tr(a.reason)}</span>
      {open && a.trades.length > 0 && <TradeRows trades={a.trades} money={money} />}
      {open && a.cost > 0 && <span className="small muted">{tr({ en: `Cost ${money(a.cost)}`, fr: `Frais ${money(a.cost)}` })}</span>}
    </li>
  );
  return (
    <Card title={tr({ en: 'What it did', fr: 'Ce qu’elle a fait' })} className="strategy-activity" actions={latest.length > 4 ? (
      <button type="button" className="btn ghost btn-sm" aria-haspopup="dialog" onClick={e => sheet.show(e.currentTarget)}>
        {tr({ en: `All ${latest.length}`, fr: `Les ${latest.length}` })}
      </button>
    ) : undefined}>
      {latest.length === 0
        ? <p className="small muted">{tr({ en: 'The trigger never fired in this window.', fr: 'Le déclencheur ne s’est jamais activé sur cette période.' })}</p>
        : <ol className="activity-list">{latest.slice(0, 4).map(a => row(a, false))}</ol>}
      <Sheet open={sheet.open} origin={sheet.origin} onClose={sheet.hide} title={tr({ en: 'What it did', fr: 'Ce qu’elle a fait' })}>
        {sheet.open && (
          <>
            {sim.actionsTruncated && <p className="figure-note">{tr({ en: 'The latest 200 actions are listed.', fr: 'Les 200 dernières actions sont listées.' })}</p>}
            <ol className="activity-list">{latest.map(a => row(a, true))}</ol>
          </>
        )}
      </Sheet>
    </Card>
  );
}
