'use client';
import { useMemo, useState, type FormEvent } from 'react';
import { GEOGRAPHIC_AREAS, WORLD_MODES, geographicCountries, type WorldMode } from '../../lib/world';
import { countryName } from '../../lib/geo';
import { buildSuggestIndex, fold, rankSuggestions, type Suggestion } from '../../lib/suggest';
import { useApp } from '../../state/app';
import { SuggestInput } from '../../components/ui/SuggestInput';

export function WorldNavigation({ mode, onMode, onCountry, area, onArea, bbox, onBbox }: {
  mode: WorldMode; onMode: (mode: WorldMode) => void; onCountry: (country: string) => void;
  area: string; onArea: (area: string) => void; bbox: string; onBbox: (bbox: string) => void;
}) {
  const { tr, lang } = useApp();
  const [search, setSearch] = useState('');
  const [noMatch, setNoMatch] = useState(false);
  // Ranked locally like every search field: ISO code or name, case and accents ignored ("etats" finds États-Unis).
  const countries = useMemo<Suggestion[]>(() => geographicCountries(lang).map(row => ({ value: row.iso3, label: countryName(row.iso3, lang) ?? '' })), [lang]);
  const index = useMemo(() => buildSuggestIndex(countries), [countries]);
  const matches = useMemo(() => (search.trim() ? rankSuggestions(index, search, 8) : []), [index, search]);
  const choose = (iso3: string) => { onCountry(iso3); setSearch(''); setNoMatch(false); };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const typed = fold(search.trim());
    const exact = countries.find(row => fold(row.value) === typed || fold(row.label) === typed);
    const only = matches.length === 1 ? matches[0] : undefined;
    if (exact) choose(exact.value);
    else if (only) choose(only.value);
    else setNoMatch(true);
  };
  const description = WORLD_MODES.find(item => item.id === mode)!;
  return (
    <section className="world-navigation" aria-label={tr({ en: 'Explorer modes and geographic navigation', fr: 'Modes et navigation géographique' })}>
      <div className="world-mode-grid" role="group" aria-label={tr({ en: 'Explorer mode', fr: 'Mode de l’explorateur' })}>
        {WORLD_MODES.map(item => <button key={item.id} type="button" className="btn ghost btn-sm" aria-pressed={mode === item.id}
          onClick={() => onMode(item.id)}>{tr(item.title)}</button>)}
      </div>
      <p className="small muted" role="status">{tr(description.note)}</p>
      <div className="world-navigation-fields">
        <form onSubmit={submit} className="field">
          <label htmlFor="world-geographic-search">{tr({ en: 'Find a country or territory', fr: 'Trouver un pays ou territoire' })}</label>
          <div className="world-search-row">
            <SuggestInput id="world-geographic-search" type="search" value={search} maxLength={80} aria-describedby="world-geographic-note"
              suggestions={countries} listLabel={tr({ en: 'Matching countries', fr: 'Pays correspondants' })}
              onPick={row => choose(row.value)} onChange={value => { setSearch(value); setNoMatch(false); }} />
            <button type="submit" className="btn ghost btn-sm">{tr({ en: 'Open', fr: 'Ouvrir' })}</button>
          </div>
          {noMatch && <p role="alert" className="small">{tr({ en: 'Choose a matching country below or enter its three-letter ISO code.', fr: 'Choisissez un pays correspondant ci-dessous ou entrez son code ISO de trois lettres.' })}</p>}
          <p id="world-geographic-note" className="small muted">{tr({ en: 'Local country search. Map navigation does not imply source or market coverage.', fr: 'Recherche locale des pays. La navigation cartographique n’implique aucune couverture des sources ou marchés.' })}</p>
        </form>
        <div className="field">
          <label htmlFor="world-region">{tr({ en: 'Regional geographic area', fr: 'Zone géographique régionale' })}</label>
          <select id="world-region" value={area} onChange={event => onArea(event.target.value)}>
            <option value="">{tr({ en: 'Worldwide', fr: 'Monde entier' })}</option>
            {GEOGRAPHIC_AREAS.map(row => <option key={row.id} value={row.id}>{tr(row.title)}</option>)}
          </select>
          <p className="small muted">{tr({ en: 'Regions use navigation boxes, which can overlap. Events are queried by source coordinates; facilities and hazards follow the same box.', fr: 'Les régions utilisent des rectangles de navigation pouvant se chevaucher. Les coordonnées sourcées filtrent les événements, installations et aléas.' })}</p>
        </div>
        <div className="field">
          <label htmlFor="world-bbox">{tr({ en: 'Custom geographic box', fr: 'Rectangle géographique personnalisé' })}</label>
          <input id="world-bbox" type="text" value={bbox} placeholder="-25,-40,60,38" maxLength={120} onChange={event => onBbox(event.target.value)} />
          <p className="small muted">{tr({ en: 'West, south, east, north. West greater than east crosses the date line. Apply filters to query the box.', fr: 'Ouest, sud, est, nord. Un ouest supérieur à l’est traverse la ligne de changement de date. Appliquez les filtres pour interroger la zone.' })}</p>
        </div>
      </div>
    </section>
  );
}
