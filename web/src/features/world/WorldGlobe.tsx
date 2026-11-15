'use client';
/**
 * World stage (T15): the globe, large, on a dark "space" panel, with a side column that says where the
 * portfolio's money is, what is selected and how to read the globe. The globe is an alternate view of
 * the feed, never the only way to select an event: the side list and the feed below are the keyboard
 * and screen-reader path. Without WebGL, or if the globe chunk fails, the side column still works.
 * Country outlines come from the site's own origin (public/geo, Natural Earth, public domain).
 */
import dynamic from 'next/dynamic';
import { Pause, Play } from 'lucide-react';
import { Component, useCallback, useEffect, useState, type ReactNode } from 'react';
import type { EventCategory, WorldEvent, WorldExposureResponse } from '../../contracts/types';
import { useApp } from '../../state/app';
import { EVENT_CATEGORY, labelOf } from '../../lib/labels';
import { fmtDate, fmtPct } from '../../lib/format';
import { countryLabel, decodeCountries, isKnownIso3, type CountryFeature, type Topology } from '../../lib/geo';
import { CATEGORY_COLORS, EXPOSURE_BREAKS, EXPOSURE_COLORS, PIN_COLORS, type GlobePin } from './globeStyle';
import type { GlobeViewProps } from './GlobeView';

function GlobeLoading() {
  const { tr } = useApp();
  return <div className="globe-loading" role="status">{tr({ en: 'Loading the globe…', fr: 'Chargement du globe…' })}</div>;
}

const GlobeView = dynamic<GlobeViewProps>(() => import('./GlobeView'), { ssr: false, loading: () => <GlobeLoading /> });

export function webglAvailable(): boolean {
  try {
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('webgl2') ?? canvas.getContext('webgl');
    if (!context) return false;
    context.getExtension('WEBGL_lose_context')?.loseContext();
    return true;
  } catch {
    return false;
  }
}

/** Follows the animation setting first, then `prefers-reduced-motion`, including changes while open. */
export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(true);
  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => {
      const anim = document.documentElement.dataset.anim;
      setReduced(anim === 'off' || (anim !== 'on' && query.matches));
    };
    update();
    query.addEventListener('change', update);
    const observer = new MutationObserver(update);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-anim'] });
    return () => { query.removeEventListener('change', update); observer.disconnect(); };
  }, []);
  return reduced;
}

class GlobeBoundary extends Component<{ fallback: ReactNode; children: ReactNode }, { failed: boolean }> {
  override state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  override render() { return this.state.failed ? this.props.fallback : this.props.children; }
}

type Geography = { status: 'loading' } | { status: 'ready'; countries: CountryFeature[] } | { status: 'failed' };

export interface WorldGlobeProps {
  pins: readonly GlobePin[];
  selectedId: string | null;
  selectedCountry: string | null;
  selectedEvent: WorldEvent | null;
  exposure: ReadonlyMap<string, number> | null;
  exposureRows: WorldExposureResponse['items'];
  counts: { shown: number; total: number | null; linked: number };
  showHazards: boolean;
  /** What the loaded hazards layer contains (its API title). */
  hazardsLabel: string;
  onPin: (pin: GlobePin) => void;
  onCountry: (iso3: string) => void;
  onOpenDetails: () => void;
}

export function WorldGlobe({
  pins, selectedId, selectedCountry, selectedEvent, exposure, exposureRows, counts, showHazards, hazardsLabel, onPin, onCountry, onOpenDetails,
}: WorldGlobeProps) {
  const { tr, lang } = useApp();
  const [webgl, setWebgl] = useState<boolean | null>(null);
  const [geography, setGeography] = useState<Geography>({ status: 'loading' });
  const [rotate, setRotate] = useState(true);
  const [hover, setHover] = useState<string | null>(null);
  const [height, setHeight] = useState(520);
  const reducedMotion = useReducedMotion();
  const stopRotation = useCallback(() => setRotate(false), []);

  useEffect(() => { setWebgl(webglAvailable()); }, []);
  useEffect(() => { setHover(null); }, [lang]);
  useEffect(() => {
    const update = () => setHeight(window.innerWidth < 768 ? 340 : window.innerWidth < 1100 ? 440 : 540);
    update();
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  }, []);

  useEffect(() => {
    if (!webgl) return undefined;
    const controller = new AbortController();
    fetch('/geo/countries-110m.json', { signal: controller.signal })
      .then(response => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json() as Promise<Topology>;
      })
      .then(topology => setGeography({ status: 'ready', countries: decodeCountries(topology) }))
      .catch(() => { if (!controller.signal.aborted) setGeography({ status: 'failed' }); });
    return () => controller.abort();
  }, [webgl]);

  const countries = geography.status === 'ready' ? geography.countries : [];
  const rows = [...exposureRows].filter(row => isKnownIso3(row.countryIso3)).sort((a, b) => b.weightPct - a.weightPct);
  const maxWeight = Math.max(1, ...rows.map(row => row.weightPct));
  const categories = [...new Set(pins.filter(p => p.kind === 'event' && p.category).map(p => p.category as EventCategory))];
  const selectedRow = selectedCountry ? rows.find(row => row.countryIso3 === selectedCountry) : undefined;

  const globe = webgl === null ? <GlobeLoading /> : !webgl ? (
    <p className="globe-fallback">{tr({ en: 'This browser has no WebGL, so the globe is off. The list beside it and the feed below show the same events and countries.', fr: 'Ce navigateur n’a pas WebGL : le globe est désactivé. La liste à côté et le fil en dessous montrent les mêmes événements et pays.' })}</p>
  ) : (
    <GlobeBoundary fallback={<p className="globe-fallback">{tr({ en: 'The globe could not be loaded. The list beside it and the feed below show the same events and countries.', fr: 'Le globe n’a pas pu être chargé. La liste à côté et le fil en dessous montrent les mêmes événements et pays.' })}</p>}>
      <GlobeView pins={pins} selectedId={selectedId} selectedCountry={selectedCountry} countries={countries} exposure={exposure}
        rotate={rotate} reducedMotion={reducedMotion} lang={lang} height={height}
        onPin={onPin} onCountry={onCountry} onHover={setHover} onInteract={stopRotation} />
    </GlobeBoundary>
  );

  return (
    <section className="world-stage" aria-label={tr({ en: 'World map of the events and of the portfolio’s countries', fr: 'Carte du monde des événements et des pays du portefeuille' })}>
      <div className="stage-globe" aria-hidden="true">
        {globe}
        <div className="stage-overlay stage-top">
          <span className="stage-chip">
            {counts.total !== null
              ? tr({ en: `${counts.shown} events, ${counts.linked} linked to the portfolio`, fr: `${counts.shown} événements, ${counts.linked} liés au portefeuille` })
              : tr({ en: 'Loading events…', fr: 'Chargement des événements…' })}
          </span>
        </div>
        <p className="stage-overlay stage-hover">{hover ?? tr({ en: 'Drag to turn, scroll to zoom, click a country or a spike', fr: 'Glissez pour tourner, molette pour zoomer, cliquez un pays ou un pic' })}</p>
      </div>
      {webgl && !reducedMotion && (
        <button type="button" className="stage-rotate" onClick={() => setRotate(v => !v)} aria-pressed={rotate}
          aria-label={rotate ? tr({ en: 'Pause rotation', fr: 'Arrêter la rotation' }) : tr({ en: 'Rotate the globe', fr: 'Faire tourner le globe' })}>
          {rotate ? <Pause aria-hidden="true" size={16} strokeWidth={2} /> : <Play aria-hidden="true" size={16} strokeWidth={2} />}
        </button>
      )}

      <div className="stage-side">
        {selectedEvent ? (
          <div className="stage-card" aria-live="polite">
            <p className="stage-kicker">
              <span className="stage-dot" style={{ background: CATEGORY_COLORS[selectedEvent.category] }} aria-hidden="true" />
              {labelOf(EVENT_CATEGORY, selectedEvent.category, lang)}, {fmtDate(selectedEvent.occurredAt.slice(0, 10), lang)}
            </p>
            <h2 className="stage-title">{selectedEvent.title}</h2>
            {selectedEvent.relatedCountries.length > 0 && (
              <p className="stage-text">{tr({ en: 'Names', fr: 'Concerne' })} {selectedEvent.relatedCountries.map(c => countryLabel(c, lang)).join(', ')}</p>
            )}
            <button type="button" className="btn btn-sm" onClick={onOpenDetails}>{tr({ en: 'Sources and linked holdings', fr: 'Sources et positions liées' })}</button>
          </div>
        ) : selectedCountry ? (
          <div className="stage-card" aria-live="polite">
            <p className="stage-kicker">{tr({ en: 'Country', fr: 'Pays' })}</p>
            <h2 className="stage-title">{countryLabel(selectedCountry, lang)}</h2>
            <p className="stage-text">
              {selectedRow
                ? tr({ en: `${fmtPct(selectedRow.weightPct, lang)} of the portfolio, through ${selectedRow.holdings.map(h => h.ticker).join(', ')}.`, fr: `${fmtPct(selectedRow.weightPct, lang)} du portefeuille, via ${selectedRow.holdings.map(h => h.ticker).join(', ')}.` })
                : tr({ en: 'No holding is listed in this country.', fr: 'Aucune position n’est cotée dans ce pays.' })}
            </p>
            <button type="button" className="btn btn-sm" onClick={onOpenDetails}>{tr({ en: 'Country details', fr: 'Détails du pays' })}</button>
          </div>
        ) : null}

        <div className="stage-block">
          <h2 className="stage-heading">{tr({ en: 'Where the money is', fr: 'Où est l’argent' })}</h2>
          {rows.length === 0 ? <p className="stage-text">{tr({ en: 'No country exposure returned.', fr: 'Aucune exposition par pays renvoyée.' })}</p> : (
            <ul className="stage-exposure">
              {rows.slice(0, 6).map(row => (
                <li key={row.countryIso3}>
                  <button type="button" className="stage-row" aria-pressed={row.countryIso3 === selectedCountry} onClick={() => onCountry(row.countryIso3)}>
                    <span className="stage-row-name">{countryLabel(row.countryIso3, lang)}</span>
                    <span className="stage-bar" aria-hidden="true"><span style={{ width: `${(row.weightPct / maxWeight) * 100}%` }} /></span>
                    <span className="stage-row-value">{fmtPct(row.weightPct, lang)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <p className="stage-note">{tr({ en: 'By listing country, not economic exposure.', fr: 'Par pays de cotation, pas l’exposition économique.' })}</p>
        </div>

        <div className="stage-block">
          <h2 className="stage-heading">{tr({ en: 'Reading the globe', fr: 'Lire le globe' })}</h2>
          <ul className="stage-legend">
            <li><span className="stage-ramp" aria-hidden="true">{EXPOSURE_COLORS.map(c => <span key={c} style={{ background: c }} />)}</span>
              {tr({ en: `Share of the portfolio (${EXPOSURE_BREAKS[0]}, ${EXPOSURE_BREAKS[1]}, ${EXPOSURE_BREAKS[2]} %)`, fr: `Part du portefeuille (${EXPOSURE_BREAKS[0]}, ${EXPOSURE_BREAKS[1]}, ${EXPOSURE_BREAKS[2]} %)` })}</li>
            <li><span className="stage-spike" aria-hidden="true" />{tr({ en: 'Event: the taller, the more important', fr: 'Événement : plus il est haut, plus il est important' })}</li>
            <li><span className="stage-arc" aria-hidden="true" />{tr({ en: 'Link to a country where you hold assets', fr: 'Lien vers un pays où vous détenez des actifs' })}</li>
            {categories.map(category => (
              <li key={category}><span className="stage-dot" style={{ background: CATEGORY_COLORS[category] }} aria-hidden="true" />{labelOf(EVENT_CATEGORY, category, lang)}</li>
            ))}
            {showHazards && <li><span className="stage-dot" style={{ background: PIN_COLORS.hazard }} aria-hidden="true" />{hazardsLabel}</li>}
          </ul>
          <p className="stage-note">{tr({ en: 'A link is a documented match, not proof of impact.', fr: 'Un lien est une correspondance documentée, pas une preuve d’impact.' })}</p>
        </div>
      </div>
    </section>
  );
}
