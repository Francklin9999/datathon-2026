'use client';
/**
 * World stage (T15): the globe, large, on a dark "space" panel, with a side column that says where the
 * portfolio's money is, what is selected and how to read the globe. The globe is an alternate view of
 * the feed, never the only way to select an event: the side list and the feed below are the keyboard
 * and screen-reader path. Without WebGL, or if the globe chunk fails, the side column still works.
 * Country outlines come from the site's own origin (public/geo, Natural Earth, public domain).
 * The stage can go full screen: the browser's own full screen where it is allowed, else a cover of the
 * window (Escape closes both).
 */
import dynamic from 'next/dynamic';
import { Maximize2, Minimize2, Pause, Play } from 'lucide-react';
import { Component, useCallback, useEffect, useRef, useState, type ReactNode, type RefObject } from 'react';
import type { EventCategory, WorldEvent, WorldExposureResponse } from '../../contracts/types';
import { profileKey, useApp } from '../../state/app';
import { EVENT_CATEGORY, labelOf } from '../../lib/labels';
import { fmtDate, fmtPct } from '../../lib/format';
import { countryLabel, decodeCountries, isKnownIso3, regionIso3, type CountryFeature, type Topology } from '../../lib/geo';
import { CATEGORY_COLORS, EXPOSURE_BREAKS, EXPOSURE_COLORS, OBSERVATION_COLORS, PIN_COLORS, pinColor, type GlobeHover, type GlobePin } from './globeStyle';
import type { InvestorMapEntry } from './investorMap';
import type { GlobeViewProps, MapCommand } from './GlobeView';
import { eventSummary, WORLD_MODES, type GeographicArea } from '../../lib/world';
import { sourceLang } from './WorldPanels';

function GlobeLoading() {
  const { tr } = useApp();
  return <div className="globe-loading" role="status">{tr({ en: 'Loading the globe…', fr: 'Chargement du globe…' })}</div>;
}

const GlobeView = dynamic<GlobeViewProps>(() => import('./GlobeView'), { ssr: false, loading: () => <GlobeLoading /> });

function webglAvailable(): boolean {
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
function useReducedMotion(): boolean {
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

/**
 * True while nothing on the globe needs to move: the stage is off-screen, the tab is hidden, or a sheet
 * (portalled to the body) covers the page.
 */
function useGlobeIdle(stageRef: RefObject<HTMLElement | null>, active: boolean): boolean {
  const [offscreen, setOffscreen] = useState(false);
  const [hidden, setHidden] = useState(false);
  const [covered, setCovered] = useState(false);
  useEffect(() => {
    const stage = stageRef.current;
    if (!active || !stage || typeof IntersectionObserver === 'undefined') { setOffscreen(false); return undefined; }
    const observer = new IntersectionObserver(([entry]) => setOffscreen(entry ? !entry.isIntersecting : false));
    observer.observe(stage);
    return () => observer.disconnect();
  }, [stageRef, active]);
  useEffect(() => {
    const updateHidden = () => setHidden(document.visibilityState === 'hidden');
    const updateCovered = () => setCovered(document.querySelector('body > .sheet-layer') !== null);
    updateHidden();
    updateCovered();
    document.addEventListener('visibilitychange', updateHidden);
    const observer = new MutationObserver(updateCovered);
    observer.observe(document.body, { childList: true });
    return () => { document.removeEventListener('visibilitychange', updateHidden); observer.disconnect(); };
  }, []);
  return offscreen || hidden || covered;
}

class GlobeBoundary extends Component<{ fallback: ReactNode; children: ReactNode }, { failed: boolean }> {
  override state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  override render() { return this.state.failed ? this.props.fallback : this.props.children; }
}

type Geography = { status: 'loading' } | { status: 'ready'; countries: CountryFeature[] } | { status: 'failed' };

export interface WorldGlobeProps {
  area: GeographicArea | null;
  onViewport: (bbox: string) => void;
  pins: readonly GlobePin[];
  investors: readonly InvestorMapEntry[];
  investorPins: readonly GlobePin[];
  selectedId: string | null;
  selectedGeometry: Record<string, unknown> | null;
  selectedCountry: string | null;
  selectedEvent: WorldEvent | null;
  exposure: ReadonlyMap<string, number> | null;
  exposureRows: WorldExposureResponse['items'];
  counts: { shown: number; total: number | null; linked: number; observations: number; loading: boolean; partial: boolean };
  showHazards: boolean;
  /** What the loaded hazards layer contains (its API title). */
  hazardsLabel: string;
  onPin: (pin: GlobePin) => void;
  onCountry: (iso3: string) => void;
  onOpenDetails: () => void;
}

export function WorldGlobe({
  pins, investors, investorPins, selectedId, selectedGeometry, selectedCountry, selectedEvent, exposure, exposureRows, counts, showHazards, hazardsLabel, onPin, onCountry, onOpenDetails, area, onViewport,
}: WorldGlobeProps) {
  const app = useApp();
  const { tr, lang } = app;
  const scope = profileKey(app);
  const [webgl, setWebgl] = useState<boolean | null>(null);
  const [geography, setGeography] = useState<Geography>({ status: 'loading' });
  const [rotate, setRotate] = useState(true);
  const [hover, setHover] = useState<GlobeHover | null>(null);
  const [height, setHeight] = useState(520);
  const [showGlobe, setShowGlobe] = useState(true);
  const [command, setCommand] = useState<MapCommand | null>(null);
  const [clusterCount, setClusterCount] = useState(0);
  const [globeReady, setGlobeReady] = useState(false);
  const markGlobeReady = useCallback(() => setGlobeReady(true), []);
  const control = (action: MapCommand['action']) => { setRotate(false); setCommand(previous => ({ action, sequence: (previous?.sequence ?? 0) + 1 })); };
  const reducedMotion = useReducedMotion();
  const stopRotation = useCallback(() => setRotate(false), []);
  const stageRef = useRef<HTMLElement | null>(null);
  // Full screen: 'native' = the browser's, 'cover' = the stage fixed over the window (no Fullscreen API).
  const [expanded, setExpanded] = useState<false | 'native' | 'cover'>(false);
  const idle = useGlobeIdle(stageRef, showGlobe);

  useEffect(() => { setWebgl(webglAvailable()); }, []);
  useEffect(() => { setHover(null); }, [lang, selectedId, scope]);
  useEffect(() => {
    const update = () => setHeight(expanded ? window.innerHeight : window.innerWidth < 768 ? 340 : window.innerWidth < 1100 ? 440 : 540);
    update();
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  }, [expanded]);

  // Runs again whenever the globe is shown or hidden: hiding it unmounts the stage element.
  useEffect(() => {
    const stage = stageRef.current;
    const sync = () => setExpanded(current => (document.fullscreenElement && document.fullscreenElement === stage ? 'native' : current === 'native' ? false : current));
    document.addEventListener('fullscreenchange', sync);
    return () => {
      document.removeEventListener('fullscreenchange', sync);
      if (stage && document.fullscreenElement === stage) void document.exitFullscreen().catch(() => undefined);
    };
  }, [showGlobe]);
  // The window cover closes with Escape, and the page behind it does not scroll.
  useEffect(() => {
    if (expanded !== 'cover') return undefined;
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') setExpanded(false); };
    const root = document.documentElement;
    const overflow = root.style.overflow;
    root.style.overflow = 'hidden';
    // The shell's bars sit in a higher stacking layer than the page: they hide while the cover is up.
    root.dataset.globeCover = '';
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('keydown', onKey); root.style.overflow = overflow; delete root.dataset.globeCover; };
  }, [expanded]);

  const exitExpanded = useCallback(async () => {
    if (expanded === 'native') await document.exitFullscreen().catch(() => undefined);
    else if (expanded === 'cover') setExpanded(false);
  }, [expanded]);
  const toggleExpanded = useCallback(() => {
    const stage = stageRef.current;
    if (!stage) return;
    if (expanded) { void exitExpanded(); return; }
    if (document.fullscreenEnabled && typeof stage.requestFullscreen === 'function') {
      // Refused, or left unanswered by an embedding browser: cover the window instead.
      let settled = false;
      stage.requestFullscreen().then(() => { settled = true; }, () => { settled = true; setExpanded('cover'); });
      window.setTimeout(() => { if (!settled && document.fullscreenElement !== stage) setExpanded('cover'); }, 500);
    } else {
      setExpanded('cover');
    }
  }, [expanded, exitExpanded]);
  // Leave full screen before opening a dialog in the page's portal layer.
  const openDetails = useCallback(() => {
    if (!expanded) { onOpenDetails(); return; }
    void exitExpanded().then(onOpenDetails);
  }, [expanded, exitExpanded, onOpenDetails]);
  const pickPin = useCallback((pin: GlobePin) => {
    setHover(null);
    setRotate(false);
    if (pin.kind !== 'cluster' && expanded) void exitExpanded().then(() => onPin(pin));
    else onPin(pin);
  }, [expanded, exitExpanded, onPin]);

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
  const observationModes = [...new Set(pins.flatMap(pin => pin.observation ? [pin.observation.mode] : []))];
  const previewEvent = hover?.pin?.event;
  const previewObservation = hover?.pin?.observation;
  const previewReference = hover?.pin?.reference;
  const previewInvestor = hover?.pin?.investorLocation;
  const previewAssessment = previewObservation?.assessment ?? previewReference?.assessment;
  const selectedRow = selectedCountry ? rows.find(row => regionIso3(row.countryIso3) === selectedCountry) : undefined;

  const globe = webgl === null ? <GlobeLoading /> : !webgl ? (
    <p className="globe-fallback">{tr({ en: 'This browser has no WebGL, so the globe is off. The list beside it and the feed below show the same events and countries.', fr: 'Ce navigateur n’a pas WebGL : le globe est désactivé. La liste à côté et le fil en dessous montrent les mêmes événements et pays.' })}</p>
  ) : (
    <GlobeBoundary fallback={<p className="globe-fallback">{tr({ en: 'The globe could not be loaded. The list beside it and the feed below show the same events and countries.', fr: 'Le globe n’a pas pu être chargé. La liste à côté et le fil en dessous montrent les mêmes événements et pays.' })}</p>}>
      <GlobeView pins={pins} investors={investors} selectedProfileId={app.profile?.profileId ?? null} selectedId={selectedId} selectedGeometry={selectedGeometry} selectedCountry={selectedCountry} countries={countries} exposure={exposure}
        rotate={rotate && !hover?.pin && !idle} paused={idle} reducedMotion={reducedMotion} lang={lang} height={height}
        onPin={pickPin} onCountry={onCountry} onHover={setHover} onInteract={stopRotation} area={area} command={command} onClusters={setClusterCount} onViewport={onViewport} onReady={markGlobeReady} />
    </GlobeBoundary>
  );

  return (
    <>
    <button type="button" className="btn ghost btn-sm world-globe-toggle" data-tour="world-globe-toggle" aria-expanded={showGlobe} aria-controls="world-map-stage" onClick={() => { setCommand(null); setGlobeReady(false); setHover(null); setShowGlobe(value => !value); }}>
      {showGlobe ? tr({ en: 'Hide globe', fr: 'Masquer le globe' }) : tr({ en: 'Show globe', fr: 'Afficher le globe' })}
    </button>
    {showGlobe &&
    <section ref={stageRef} className="world-stage" data-tour="world-globe" data-expanded={expanded || undefined}
      aria-label={tr({ en: 'World map of the events and of the portfolio’s countries', fr: 'Carte du monde des événements et des pays du portefeuille' })}>
      <div id="world-map-stage" className="stage-globe" aria-hidden="true">
        {globe}
        <div className="stage-overlay stage-top">
          <span className="stage-chip">
            {counts.total !== null
              ? counts.loading
                ? tr({ en: `Loading all events… ${counts.shown} of ${counts.total}`, fr: `Chargement de tous les événements… ${counts.shown} sur ${counts.total}` })
                : counts.partial
                ? tr({ en: `${counts.shown} of ${counts.total} events available`, fr: `${counts.shown} événements disponibles sur ${counts.total}` })
                : tr({ en: `${counts.shown} events, ${counts.linked} linked to the portfolio`, fr: `${counts.shown} événements, ${counts.linked} liés au portefeuille` })
              : tr({ en: 'Loading events…', fr: 'Chargement des événements…' })}
          </span>
          {counts.observations > 0 && <span className="stage-chip world-data-chip">
            {tr({ en: `+ ${counts.observations} source data points`, fr: `+ ${counts.observations} points de données sourcées` })}
          </span>}
        </div>
        {(previewEvent || previewObservation || previewReference || previewInvestor) && hover && <div className="world-event-hover" role="tooltip" style={{
          left: Math.max(12, Math.min((hover.x ?? 12) + 18, (hover.width ?? 324) - 312)),
          top: Math.max(12, Math.min((hover.y ?? 12) + 18, height - 260)),
        }}>
          <p className="world-hover-meta">
            <span className="stage-dot" style={{ background: pinColor(hover.pin!, null) }} />
            {previewEvent ? labelOf(EVENT_CATEGORY, previewEvent.category, lang)
              : previewObservation ? tr(WORLD_MODES.find(mode => mode.id === previewObservation.mode)!.title)
              : previewReference ? tr(previewReference.sourceName) : tr({ en: 'Fictional location', fr: 'Lieu fictif' })}
          </p>
          <strong className="world-hover-title" lang={previewEvent ? sourceLang(previewEvent) : undefined}>{hover.pin?.label}</strong>
          <p className="world-hover-summary">{previewEvent ? eventSummary(previewEvent, lang)
            : previewObservation?.summary ?? (previewReference ? tr(previewReference.summary) : previewInvestor ? `${previewInvestor.location}, ${previewInvestor.country}` : null)}</p>
          {previewEvent?.portfolioRelevant !== undefined && <p className="world-hover-exposure">
            {previewEvent.portfolioRelevant
              ? tr({ en: 'Portfolio match identified', fr: 'Correspondance avec le portefeuille' })
              : tr({ en: 'No portfolio match in the event feed', fr: 'Aucune correspondance dans le fil d’événements' })}
          </p>}
          {previewAssessment && previewAssessment.profileId === app.profile?.profileId && <p className="world-hover-exposure">
            {previewAssessment.exposures.length
              ? tr({ en: `Potential exposure · ${fmtPct(previewAssessment.matchedWeightPct, lang)} matched`, fr: `Exposition potentielle · ${fmtPct(previewAssessment.matchedWeightPct, lang)} correspondant` })
              : tr({ en: 'No portfolio match in the available data', fr: 'Aucune correspondance dans les données disponibles' })}
          </p>}
          <p className="world-hover-hint">{previewEvent
            ? tr({ en: 'Click for event details and portfolio exposure', fr: 'Cliquez pour les détails et l’exposition du portefeuille' })
            : previewInvestor ? tr({ en: 'Click for location details', fr: 'Cliquez pour les détails du lieu' })
            : tr({ en: 'Click for source data and portfolio exposure', fr: 'Cliquez pour les données sourcées et l’exposition du portefeuille' })}</p>
        </div>}
        <p className="stage-overlay stage-hover">{hover?.pin?.event
          ? tr({ en: 'Click the event to inspect your portfolio’s exposure', fr: 'Cliquez sur l’événement pour examiner l’exposition du portefeuille' })
          : hover?.label ?? tr({ en: 'Drag to turn, scroll to zoom, hover to preview, click for details', fr: 'Glissez pour tourner, molette pour zoomer, survolez pour un aperçu, cliquez pour les détails' })}</p>
      </div>
      {webgl && (
        <div className="stage-controls">
          {!reducedMotion && (
            <button type="button" className="stage-btn" onClick={() => setRotate(v => !v)} aria-pressed={rotate}
              aria-label={rotate ? tr({ en: 'Pause rotation', fr: 'Arrêter la rotation' }) : tr({ en: 'Rotate the globe', fr: 'Faire tourner le globe' })}
              title={rotate ? tr({ en: 'Pause rotation', fr: 'Arrêter la rotation' }) : tr({ en: 'Rotate the globe', fr: 'Faire tourner le globe' })}>
              {rotate ? <Pause aria-hidden="true" size={16} strokeWidth={2} /> : <Play aria-hidden="true" size={16} strokeWidth={2} />}
            </button>
          )}
          <button type="button" className="stage-btn" onClick={toggleExpanded} aria-pressed={Boolean(expanded)}
            aria-label={expanded ? tr({ en: 'Exit full screen', fr: 'Quitter le plein écran' }) : tr({ en: 'Full screen', fr: 'Plein écran' })}
            title={expanded ? tr({ en: 'Exit full screen (Esc)', fr: 'Quitter le plein écran (Échap)' }) : tr({ en: 'Full screen', fr: 'Plein écran' })}>
            {expanded ? <Minimize2 aria-hidden="true" size={16} strokeWidth={2} /> : <Maximize2 aria-hidden="true" size={16} strokeWidth={2} />}
          </button>
        </div>
      )}

      <div className="stage-side">
        {webgl && <div className="world-map-controls" data-tour="world-map-controls" role="group" aria-label={tr({ en: 'Globe controls', fr: 'Commandes du globe' })}>
          {([
            ['zoom-in', { en: 'Zoom in', fr: 'Agrandir' }], ['zoom-out', { en: 'Zoom out', fr: 'Réduire' }],
            ['left', { en: 'West', fr: 'Ouest' }], ['right', { en: 'East', fr: 'Est' }],
            ['up', { en: 'North', fr: 'Nord' }], ['down', { en: 'South', fr: 'Sud' }],
            ['reset', { en: 'Reset view', fr: 'Réinitialiser la vue' }],
            ['query', { en: 'Query visible area', fr: 'Interroger la zone visible' }],
          ] as const).map(([action, label]) => <button key={action} type="button" className="btn ghost btn-sm" disabled={!globeReady} onClick={() => control(action)}>{tr(label)}</button>)}
          <p className="stage-note" role="status">{tr({ en: `${pins.length} loaded pins; ${clusterCount} geographic clusters at this zoom. Zoom in or click a cluster to inspect individual pins. The feed retains every loaded event.`, fr: `${pins.length} épingles chargées ; ${clusterCount} regroupements à ce zoom. Agrandissez ou cliquez un regroupement pour voir les épingles. Le fil conserve tous les événements chargés.` })}</p>
          <p className="stage-note">{tr({ en: 'Visible-area queries enclose sampled visible surface points in a geographic box. The box can include areas outside the curved globe view.', fr: 'Les requêtes de zone visible entourent des points échantillonnés de la surface visible dans un rectangle. Ce rectangle peut inclure des zones hors de la vue courbe du globe.' })}</p>
        </div>}
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
            <button type="button" className="btn btn-sm" onClick={openDetails}>{tr({ en: 'Sources and linked holdings', fr: 'Sources et positions liées' })}</button>
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
            <button type="button" className="btn btn-sm" onClick={openDetails}>{tr({ en: 'Country details', fr: 'Détails du pays' })}</button>
          </div>
        ) : null}

        {investors.length > 0 && <div className="stage-block">
          <h2 className="stage-heading">{tr({ en: 'Fictional investors and wallets', fr: 'Investisseurs et portefeuilles fictifs' })}</h2>
          <ul className="stage-exposure">{investorPins.map(pin => <li key={pin.id}>
            <button type="button" className="stage-row stage-investor-row" onClick={() => pickPin(pin)}>
              <span className="stage-dot" style={{ background: pinColor(pin, null) }} aria-hidden="true" />
              <span className="stage-row-name">{pin.investorLocation?.owner}
                {pin.investorLocation?.selected && ` (${tr({ en: 'Selected profile', fr: 'Profil sélectionné' })})`}
                {' · '}{pin.investorLocation?.kind === 'home' ? tr({ en: 'Residence', fr: 'Résidence' }) : `${tr({ en: 'Wallet custody', fr: 'Garde du portefeuille' })}: ${pin.investorLocation?.name}`}: {pin.investorLocation?.location}, {pin.investorLocation?.country}</span>
            </button></li>)}</ul>
          <p className="stage-note">{tr({ en: 'Fictional residence and custody links are separate from listing-country exposure. Larger markers identify the selected profile.', fr: 'Les liens fictifs de résidence et de garde sont distincts de l’exposition par pays de cotation. Les marqueurs plus grands désignent le profil sélectionné.' })}</p>
        </div>}

        <div className="stage-block">
          <h2 className="stage-heading">{tr({ en: 'Where the money is', fr: 'Où est l’argent' })}</h2>
          {rows.length === 0 ? <p className="stage-text">{tr({ en: 'No country exposure returned.', fr: 'Aucune exposition par pays renvoyée.' })}</p> : (
            <ul className="stage-exposure">
              {rows.slice(0, 6).map(row => (
                <li key={row.countryIso3}>
                  <button type="button" className="stage-row" aria-pressed={regionIso3(row.countryIso3) === selectedCountry} onClick={() => onCountry(row.countryIso3)}>
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
            {observationModes.map(mode => <li key={`observation:${mode}`}><span className="stage-dot" style={{ background: OBSERVATION_COLORS[mode] }} aria-hidden="true" />{tr({ en: 'Data', fr: 'Données' })}: {tr(WORLD_MODES.find(item => item.id === mode)!.title)}</li>)}
            {investors.length > 0 && <li><span className="stage-dot" style={{ background: '#F8D47A' }} aria-hidden="true" />{tr({ en: 'Fictional residence', fr: 'Résidence fictive' })}</li>}
            {investors.length > 0 && <li><span className="stage-dot" style={{ background: '#6AE0CF' }} aria-hidden="true" />{tr({ en: 'Fictional wallet custody location', fr: 'Lieu fictif de garde du portefeuille' })}</li>}
            {investors.length > 0 && <li><span className="stage-arc stage-investor-arc" aria-hidden="true" />{tr({ en: 'Fictional residence-to-wallet link', fr: 'Lien fictif entre la résidence et le portefeuille' })}</li>}
            {selectedGeometry && <li><span className="stage-dot" style={{ background: '#6AE0CF' }} aria-hidden="true" />{tr({ en: 'Selected source boundary', fr: 'Limite de source sélectionnée' })}</li>}
            <li><span className="stage-ramp" aria-hidden="true">{EXPOSURE_COLORS.map(c => <span key={c} style={{ background: c }} />)}</span>
              {tr({ en: `Share of the portfolio (${EXPOSURE_BREAKS[0]}, ${EXPOSURE_BREAKS[1]}, ${EXPOSURE_BREAKS[2]} %)`, fr: `Part du portefeuille (${EXPOSURE_BREAKS[0]}, ${EXPOSURE_BREAKS[1]}, ${EXPOSURE_BREAKS[2]} %)` })}</li>
            <li><span className="stage-spike" aria-hidden="true" />{tr({ en: 'Event: the taller, the more important', fr: 'Événement : plus il est haut, plus il est important' })}</li>
            <li><span className="stage-arc" aria-hidden="true" />{tr({ en: 'Link to a country where you hold assets', fr: 'Lien vers un pays où vous détenez des actifs' })}</li>
            {categories.map(category => (
              <li key={category}><span className="stage-dot" style={{ background: CATEGORY_COLORS[category] }} aria-hidden="true" />{labelOf(EVENT_CATEGORY, category, lang)}</li>
            ))}
            {showHazards && <li><span className="stage-dot" style={{ background: PIN_COLORS.hazard }} aria-hidden="true" />{hazardsLabel}</li>}
          </ul>
          <p className="stage-note">{tr({ en: 'Event arcs represent named-country and listing-country matches, including proxies. They do not establish business operations or financial impact.', fr: 'Les arcs des événements représentent des correspondances de pays nommés et de cotation, y compris des approximations. Ils ne prouvent ni activité commerciale ni impact financier.' })}</p>
        </div>
      </div>
    </section>
    }
    </>
  );
}
