'use client';
/**
 * Allocation donut (snapshot.byAssetGroup or byCountry). Colours follow the entity in a fixed
 * order, never the rank; more than five countries fold into "Other". Weights are display values
 * without factIds (shown as text, like the Portfolio page).
 */
import { useMemo, useState } from 'react';
import type { I18NText, Lang, OverviewResponse } from '../../contracts/types';
import { useApp } from '../../state/app';
import { Card } from '../../components/common/Page';
import { DonutChart, type DonutItem } from '../../components/ui/DonutChart';
import { SegmentedControl } from '../../components/ui/SegmentedControl';
import { ASSET_GROUP, labelOf } from '../../lib/labels';
import { fmtPct } from '../../lib/format';

type View = 'group' | 'country';
const GROUP_ORDER = ['equity', 'fixed_income', 'commodity', 'crypto', 'cash'] as const;
const COUNTRY_FIRST = ['CAN', 'USA'];
const COUNTRY_NAME: Record<string, I18NText> = {
  CAN: { en: 'Canada', fr: 'Canada' },
  USA: { en: 'United States', fr: 'États-Unis' },
};
const slot = (i: number) => `var(--cat-${i + 1})`;

function groupItems(groups: OverviewResponse['snapshot']['byAssetGroup'], lang: Lang): DonutItem[] {
  return [...groups]
    .sort((a, b) => GROUP_ORDER.indexOf(a.key) - GROUP_ORDER.indexOf(b.key))
    .map(g => ({ key: g.key, label: labelOf(ASSET_GROUP, g.key, lang), value: g.weightPct, color: slot(Math.max(0, GROUP_ORDER.indexOf(g.key))) }));
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

export function AllocationCard({ overview }: { overview: OverviewResponse }) {
  const { tr, lang } = useApp();
  const [view, setView] = useState<View>('group');
  const items = useMemo(
    () => (view === 'group'
      ? groupItems(overview.snapshot.byAssetGroup, lang)
      : countryItems(overview.snapshot.byCountry, tr, tr({ en: 'Other', fr: 'Autres' }))),
    [view, overview, lang, tr],
  );
  const title = tr({ en: 'Allocation', fr: 'Répartition' });
  return (
    <Card title={title} className="dash-card" actions={(
      <SegmentedControl<View> size="sm" value={view} onChange={setView}
        label={tr({ en: 'Group allocation by', fr: 'Regrouper la répartition par' })}
        options={[
          { value: 'group', label: tr({ en: 'Asset class', fr: 'Classe d’actifs' }) },
          { value: 'country', label: tr({ en: 'Country', fr: 'Pays' }) },
        ]} />
    )}>
      {items.length === 0
        ? <p className="small muted">{tr({ en: 'No allocation returned for this portfolio.', fr: 'Aucune répartition retournée pour ce portefeuille.' })}</p>
        : (
          <DonutChart items={items} format={v => fmtPct(v, lang)}
            centerValue={String(overview.snapshot.positions.length)}
            centerLabel={tr({ en: 'positions', fr: 'positions' })}
            label={view === 'group'
              ? tr({ en: 'Weight by asset class, % of the fictional portfolio', fr: 'Poids par classe d’actifs, % du portefeuille fictif' })
              : tr({ en: 'Weight by listing country, % of the fictional portfolio', fr: 'Poids par pays de cotation, % du portefeuille fictif' })} />
        )}
    </Card>
  );
}
