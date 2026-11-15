'use client';
import { useMemo, useState, type FormEvent } from 'react';
import { GEOGRAPHIC_AREAS, WORLD_MODES, geographicCountries, type WorldMode } from '../../lib/world';
import { useApp } from '../../state/app';

export function WorldNavigation({ mode, onMode, onCountry, area, onArea, bbox, onBbox }: {
  mode: WorldMode; onMode: (mode: WorldMode) => void; onCountry: (country: string) => void;
  area: string; onArea: (area: string) => void; bbox: string; onBbox: (bbox: string) => void;
}) {
  const { tr, lang } = useApp();
  const [search, setSearch] = useState('');
  const [noMatch, setNoMatch] = useState(false);
  const countries = useMemo(() => geographicCountries(lang), [lang]);
  const matches = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase(lang);
    return needle ? countries.filter(row => row.iso3.toLowerCase() === needle || row.label.toLocaleLowerCase(lang).includes(needle)).slice(0, 8) : [];
  }, [search, countries, lang]);
  const choose = (iso3: string) => { onCountry(iso3); setSearch(''); setNoMatch(false); };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const exact = countries.find(row => row.iso3 === search.trim().toUpperCase() || row.label.toLocaleLowerCase(lang) === search.trim().toLocaleLowerCase(lang));
    if (exact || matches.length === 1) choose((exact ?? matches[0])!.iso3);
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
            <input id="world-geographic-search" value={search} type="search" autoComplete="off" maxLength={80}
              aria-describedby="world-geographic-note" onChange={event => { setSearch(event.target.value); setNoMatch(false); }} />
            <button type="submit" className="btn ghost btn-sm">{tr({ en: 'Open', fr: 'Ouvrir' })}</button>
          </div>
          {matches.length > 0 && <ul className="world-country-results" aria-label={tr({ en: 'Matching countries', fr: 'Pays correspondants' })}>
            {matches.map(row => <li key={row.iso3}><button type="button" className="linklike" onClick={() => choose(row.iso3)}>{row.label}</button></li>)}
          </ul>}
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
