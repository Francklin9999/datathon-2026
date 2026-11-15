'use client';
/**
 * Globe container (T15). The globe is an alternate view of the feed, never the only way to select an
 * event: when WebGL is missing or the globe chunk fails to load, a text notice points to the feed and
 * tables, which stay complete. The WebGL component is loaded lazily with `ssr: false` (web/SPEC.md §4).
 * Country outlines come from the site's own origin (public/geo, Natural Earth, public domain).
 */
import dynamic from 'next/dynamic';
import { Component, useEffect, useState, type ReactNode } from 'react';
import { useApp } from '../../state/app';
import { Loading, Unavailable } from '../../components/common/States';
import { decodeCountries, type CountryFeature, type Topology } from '../../lib/geo';
import { EXPOSURE_BREAKS, EXPOSURE_COLORS, PIN_COLORS, type GlobePin } from './globeStyle';
import type { GlobeViewProps } from './GlobeView';

function GlobeLoading() {
  const { tr } = useApp();
  return <Loading label={tr({ en: 'Loading the globe…', fr: 'Chargement du globe…' })} />;
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

/** Follows `prefers-reduced-motion`, including changes while the page is open. */
export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(true);
  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReduced(query.matches);
    update();
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
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
  exposure: ReadonlyMap<string, number> | null;
  showFacilities: boolean;
  showHazards: boolean;
  /** Legend text of the hazard pins: what the loaded hazards layer contains (its API title). */
  hazardsLabel: string;
  onPin: (pin: GlobePin) => void;
  onCountry: (iso3: string) => void;
}

export function WorldGlobe({ pins, selectedId, exposure, showFacilities, showHazards, hazardsLabel, onPin, onCountry }: WorldGlobeProps) {
  const { tr, lang } = useApp();
  const [webgl, setWebgl] = useState<boolean | null>(null);
  const [geography, setGeography] = useState<Geography>({ status: 'loading' });
  const [rotate, setRotate] = useState(true);
  const [hover, setHover] = useState<string | null>(null);
  const reducedMotion = useReducedMotion();

  useEffect(() => { setWebgl(webglAvailable()); }, []);
  // A caption written in the previous language is dropped when the language changes.
  useEffect(() => { setHover(null); }, [lang]);

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

  const fallbackText = tr({
    en: 'Use the event feed, the country list and the tables on this page: they contain everything the globe would show.',
    fr: 'Utilisez le fil d’événements, la liste des pays et les tableaux de cette page : ils contiennent tout ce que le globe afficherait.',
  });

  if (webgl === null) return <GlobeLoading />;
  if (!webgl) {
    return (
      <Unavailable title={tr({ en: 'The globe is not available: this browser has no WebGL.', fr: 'Le globe n’est pas disponible : ce navigateur n’a pas WebGL.' })}>
        {fallbackText}
      </Unavailable>
    );
  }

  const countries = geography.status === 'ready' ? geography.countries : [];
  const swatch = (color: string) => <span className="swatch swatch-dot" style={{ background: color }} aria-hidden="true" />;

  return (
    <div className="globe-wrap">
      <GlobeBoundary fallback={(
        <Unavailable title={tr({ en: 'The globe could not be loaded.', fr: 'Le globe n’a pas pu être chargé.' })}>{fallbackText}</Unavailable>
      )}>
        <div role="group" aria-label={tr({ en: 'Globe view of the events in the feed. The feed below it is the keyboard and screen-reader path to the same events.', fr: 'Vue en globe des événements du fil. Le fil est le chemin au clavier et au lecteur d’écran vers les mêmes événements.' })}>
          <GlobeView pins={pins} selectedId={selectedId} countries={countries} exposure={exposure} rotate={rotate}
            reducedMotion={reducedMotion} lang={lang} onPin={onPin} onCountry={onCountry} onHover={setHover} />
        </div>
      </GlobeBoundary>
      <p className="small globe-caption" aria-hidden="true">{hover ?? tr({ en: 'Point at a pin or a country to see its name; click to open it.', fr: 'Pointez une épingle ou un pays pour voir son nom ; cliquez pour l’ouvrir.' })}</p>
      <div className="row-actions">
        <button type="button" className="btn ghost btn-sm" aria-pressed={rotate && !reducedMotion} disabled={reducedMotion}
          onClick={() => setRotate(value => !value)}>
          {rotate && !reducedMotion ? tr({ en: 'Pause rotation', fr: 'Arrêter la rotation' }) : tr({ en: 'Rotate the globe', fr: 'Faire tourner le globe' })}
        </button>
        {reducedMotion && <span className="small muted">{tr({ en: 'Rotation is off: your system asks for reduced motion.', fr: 'Rotation désactivée : votre système demande de réduire les animations.' })}</span>}
      </div>
      {geography.status === 'failed' && (
        <p className="small muted" role="status">{tr({ en: 'Country outlines could not be loaded; pins are shown on a plain sphere.', fr: 'Les contours des pays n’ont pas pu être chargés ; les épingles sont affichées sur une sphère unie.' })}</p>
      )}
      <ul className="legend globe-legend" aria-label={tr({ en: 'Globe legend', fr: 'Légende du globe' })}>
        <li>{swatch(PIN_COLORS.event)}{tr({ en: 'Event at a point or city', fr: 'Événement localisé à un point ou une ville' })}</li>
        <li>{swatch(PIN_COLORS.eventCountry)}{tr({ en: 'Event located only at country level (country centroid, not an exact place)', fr: 'Événement localisé seulement à l’échelle du pays (centroïde, pas un lieu exact)' })}</li>
        <li>{swatch(PIN_COLORS.selected)}{tr({ en: 'Selected event', fr: 'Événement sélectionné' })}</li>
        {showFacilities && <li>{swatch(PIN_COLORS.facility)}{tr({ en: 'Emissions facility (registry location)', fr: 'Installation émettrice (emplacement du registre)' })}</li>}
        {showHazards && <li>{swatch(PIN_COLORS.hazard)}{hazardsLabel}</li>}
        {exposure && (
          <li>
            {EXPOSURE_COLORS.map(color => <span key={color} className="swatch swatch-dot" style={{ background: color }} aria-hidden="true" />)}
            {tr({
              en: `Country shading: portfolio weight returned for that country (under ${EXPOSURE_BREAKS[0]} %, ${EXPOSURE_BREAKS[0]}–${EXPOSURE_BREAKS[1]} %, ${EXPOSURE_BREAKS[1]} % or more). Figures are in the exposure table.`,
              fr: `Teinte des pays : poids du portefeuille renvoyé pour ce pays (moins de ${EXPOSURE_BREAKS[0]} %, ${EXPOSURE_BREAKS[0]}–${EXPOSURE_BREAKS[1]} %, ${EXPOSURE_BREAKS[1]} % ou plus). Les chiffres sont dans le tableau d’exposition.`,
            })}
          </li>
        )}
      </ul>
      <p className="small muted">{tr({ en: 'A pin marks where a source places an event. Proximity to a holding or a facility is not proof of any impact on the portfolio.', fr: 'Une épingle indique où une source situe un événement. La proximité d’une position ou d’une installation ne prouve aucun impact sur le portefeuille.' })}</p>
    </div>
  );
}
