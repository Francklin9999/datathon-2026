'use client';
/**
 * Allocation donut (snapshot.byAssetGroup or byCountry). Colours follow the entity in a fixed order,
 * never the rank; more than five countries fold into "Other". The asset-class scope keeps only the
 * selected groups (weights stay shares of the whole portfolio). Weights are display values without
 * factIds, shown as text like the Portfolio page.
 */
import { useMemo, useState } from 'react';
import type { I18NText, Lang, OverviewResponse } from '../../contracts/types';
import { useApp } from '../../state/app';
import { Card } from '../../components/common/Page';
import { DonutChart, type DonutItem } from '../../components/ui/DonutChart';
import { SegmentedControl } from '../../components/ui/SegmentedControl';
import { ASSET_GROUP, labelOf } from '../../lib/labels';
import { fmtPct } from '../../lib/format';
import { ASSET_GROUPS, type DashboardScope } from '../../lib/ui/scope';

type View = 'group' | 'country';
const COUNTRY_FIRST = ['CAN', 'USA'];
const COUNTRY_NAME: Record<string, I18NText> = {
  CAN: { en: 'Canada', fr: 'Canada' },
  USA: { en: 'United States', fr: 'États-Unis' },
};
const slot = (i: number) => `var(--cat-${i + 1})`;

function groupItems(groups: OverviewResponse['snapshot']['byAssetGroup'], lang: Lang, scope: DashboardScope): DonutItem[] {
  return [...groups]
    .filter(g => scope.assetGroups.length === 0 || scope.assetGroups.includes(g.key))
    .sort((a, b) => ASSET_GROUPS.indexOf(a.key) - ASSET_GROUPS.indexOf(b.key))
    .map(g => ({ key: g.key, label: labelOf(ASSET_GROUP, g.key, lang), value: g.weightPct, color: slot(Math.max(0, ASSET_GROUPS.indexOf(g.key))) }));
}

function countryItems(countries: OverviewResponse['snapshot']['byCountry'], tr: (t: I18NText) => string, other: string): DonutItem[] {
  const codes = [...new Set(countries.map(c => c.key))];
  const order = [...COUNTRY_FIRST.filter(c => codes.includes(c)), ...codes.filter(c => !COUNTRY_FIRST.includes(c)).sort()];
  const named = order.slice(0, 5);
  const items: DonutItem[] = countries
    .filter(c => named.includes(c.key))
    .sort((a, b) => order.indexOf(a.key) - order.indexOf(b.key))
    .map(c => ({ key: c.key, label: COUNTRY_NAME[c.key] ? tr(COUNTRY_NAME[c.key]!) : c.key, value: c.weightPct, color: slot(named.indexOf(c.key)) }));
  const rest = countries.filter(c => !named.includes(c.key)).reduce((sum, c) => sum + c.weightPct, 0);
  if (rest > 0) items.push({ key: '__other', label: other, value: rest, color: 'var(--cat-other)' });
  return items;
}

export function AllocationCard({ overview, scope }: { overview: OverviewResponse; scope: DashboardScope }) {
  const { tr, lang } = useApp();
  const [view, setView] = useState<View>('group');
  const items = useMemo(
    () => (view === 'group'
      ? groupItems(overview.snapshot.byAssetGroup, lang, scope)
      : countryItems(overview.snapshot.byCountry, tr, tr({ en: 'Other', fr: 'Autres' }))),
    [view, overview, lang, tr, scope],
  );
  const filtered = view === 'group' && scope.assetGroups.length > 0;
  const inScope = items.reduce((sum, item) => sum + item.value, 0);
  return (
    <Card title={tr({ en: 'Allocation', fr: 'Répartition' })} actions={(
      <SegmentedControl<View> size="sm" value={view} onChange={setView}
        label={tr({ en: 'Group allocation by', fr: 'Regrouper la répartition par' })}
        options={[
          { value: 'group', label: tr({ en: 'Asset class', fr: 'Classe d’actifs' }) },
          { value: 'country', label: tr({ en: 'Country', fr: 'Pays' }) },
        ]} />
    )}>
      {items.length === 0
        ? <p className="small muted">{tr({ en: 'No holdings in this scope', fr: 'Aucune position dans ce périmètre' })}</p>
        : (
          <DonutChart items={items} format={v => fmtPct(v, lang)}
            centerValue={filtered ? fmtPct(inScope, lang) : String(overview.snapshot.positions.length)}
            centerLabel={filtered ? tr({ en: 'in scope', fr: 'dans le périmètre' }) : tr({ en: 'positions', fr: 'positions' })}
            label={view === 'group'
              ? tr({ en: 'Weight by asset class, % of the fictional portfolio', fr: 'Poids par classe d’actifs, % du portefeuille fictif' })
              : tr({ en: 'Weight by listing country, % of the fictional portfolio', fr: 'Poids par pays de cotation, % du portefeuille fictif' })} />
        )}
      {view === 'country' && scope.assetGroups.length > 0 && (
        <p className="alloc-note">{tr({ en: 'The country split covers the whole portfolio', fr: 'La répartition par pays couvre tout le portefeuille' })}</p>
      )}
      {scope.minWeight > 0 && (
        <p className="alloc-note">{tr({ en: 'The minimum weight applies to Positions only', fr: 'Le poids minimum s’applique seulement aux Positions' })}</p>
      )}
    </Card>
  );
}
