'use client';
/**
 * World Explorer (T15, web/page-specs/world-explorer.md): sourced events and factual exposure.
 * Fetches the layers, a paginated event page and the profile's country exposure. The feed is the
 * primary, keyboard-accessible view; the globe is an alternate view of the same loaded events
 * (thinned and labelled). Dates default to the dataset coverage returned by the API, never to "today".
 * The feed opens on events matching the portfolio; the detailed filters are folded (review §4.6).
 * Nothing here estimates a financial impact, and a failed call never falls back to fixture data.
 */
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import type {
  AirportsResponse, EventCategory, FacilitiesResponse, HazardsResponse, Period, Profile, WorldEvent, WorldEventItem,
  WorldExposureResponse, WorldLayer, WorldLayersResponse,
} from '../../contracts/types';
import { ThemeTag as THEMES } from '../../contracts/catalog';
import { getApiClient } from '../../api/index';
import { asApiError, isAbort, type ApiRequestError } from '../../api/errors';
import { profileKey, useApp } from '../../state/app';
import { useQuery } from '../../state/useQuery';
import { Card, PageHeader, ProfileGate } from '../../components/common/Page';
import { Empty, ErrorState, Loading, Unavailable } from '../../components/common/States';
import { ExternalLink } from '../../components/common/ExternalLink';
import { FactChip, FactScopeProvider, LimitationList, type FactScope } from '../../components/common/FactDrawer';
import {
  EVENT_CATEGORY, EVENT_ORIGIN, EXPOSURE_BASIS, HAZARD_TYPE, LOCATION_PRECISION, MATCH_CONFIDENCE, REGISTRY, THEME_TAG,
  WORLD_LAYER, labelOf,
} from '../../lib/labels';
import { fmtDate, fmtDateTime, fmtNumber, fmtPct } from '../../lib/format';
import { countryLabel, isKnownIso3 } from '../../lib/geo';
import {
  EMPTY_FILTERS, EVENT_CATEGORIES, EVENT_ORIGINS, GEOGRAPHIC_AREAS, WORLD_MODES, validBbox, LAYER_IDS, MAX_PINS, MAX_RANGE_DAYS, NO_LISTING_COUNTRY, spatialReferencePins, buildEventsQuery, clampRange,
  defaultRange, eventSelectionPatch, exposureFactId, filtersKey, insideBbox, isResidualExposure, layerState, mergeEventPages, mergeSelection,
  rangeIssue, selectionQuery, thinPins, visibleEvents, type LayerId, type LayerUnavailable, type RangeIssue, type WorldFilters,
  type WorldSelection, type WorldSelectionPatch, type WorldMode,
} from '../../lib/world';
import { CountryPanel, EventLine, EventPanel, sourceLang } from './WorldPanels';
import { WorldGlobe } from './WorldGlobe';
import type { GlobePin } from './globeStyle';
import { WorldNavigation } from './WorldNavigation';
import { WorldObservations } from './WorldObservations';
import './world.css';

const TITLE = { en: 'World Explorer', fr: 'Explorateur mondial' };
const THEME_TAGS = Object.values(THEMES);
const EXTRA_LAYER_LIMIT = 500;


export function WorldExplorerPage() {
  const { tr, feature, meta } = useApp();
  if (meta && !feature('world_explorer')) {
    return (
      <>
        <PageHeader title={tr(TITLE)} />
        <Unavailable title={tr({ en: 'The World Explorer is turned off in this deployment.', fr: 'L’Explorateur mondial est désactivé dans ce déploiement.' })}>
          {tr({ en: 'No event, exposure or globe is shown. The other pages remain available.', fr: 'Aucun événement, aucune exposition ni aucun globe n’est affiché. Les autres pages restent disponibles.' })}
        </Unavailable>
      </>
    );
  }
  return <ProfileGate>{profile => <WorldContent profile={profile} />}</ProfileGate>;
}

interface FeedState {
  key: string | null;
  profileId: string | null;
  items: WorldEventItem[];
  nextCursor: string | null;
  total: number | null;
  dataVersion: string | null;
  loadedAt: string | null;
  loading: boolean;
  loadingMore: boolean;
  error: ApiRequestError | null;
  moreError: ApiRequestError | null;
}
const EMPTY_FEED: FeedState = {
  key: null, profileId: null, items: [], nextCursor: null, total: null, dataVersion: null, loadedAt: null,
  loading: false, loadingMore: false, error: null, moreError: null,
};

type FormIssue = RangeIssue | 'partial' | 'country' | 'bbox';
const FORM_ISSUE: Record<FormIssue, { en: string; fr: string }> = {
  bbox: { en: 'Enter four valid coordinates: west, south, east, north. South must not exceed north.', fr: 'Entrez quatre coordonnées valides : ouest, sud, est, nord. Le sud ne doit pas dépasser le nord.' },
  format: { en: 'Both dates must be calendar dates.', fr: 'Les deux dates doivent être des dates du calendrier.' },
  order: { en: 'The start date must not be after the end date.', fr: 'La date de début ne doit pas suivre la date de fin.' },
  too_long: { en: `The interval is longer than ${MAX_RANGE_DAYS} days, the most the API accepts.`, fr: `L’intervalle dépasse ${MAX_RANGE_DAYS} jours, le maximum accepté par l’API.` },
  outside_coverage: { en: 'The interval lies entirely outside the dataset coverage.', fr: 'L’intervalle est entièrement hors de la couverture du jeu de données.' },
  partial: { en: 'Enter both a start and an end date, or neither.', fr: 'Saisissez une date de début et une date de fin, ou aucune.' },
  country: { en: 'The country must be a three-letter ISO code, for example CAN.', fr: 'Le pays doit être un code ISO de trois lettres, par exemple CAN.' },
};

const LAYER_REASON: Record<LayerUnavailable, { en: string; fr: string }> = {
  flag_off: { en: 'Unavailable: turned off in this deployment.', fr: 'Indisponible : désactivée dans ce déploiement.' },
  not_listed: { en: 'Unavailable: the API does not list this layer.', fr: 'Indisponible : l’API ne liste pas cette couche.' },
  dataset_missing: { en: 'Unavailable: its dataset is not loaded.', fr: 'Indisponible : son jeu de données n’est pas chargé.' },
};

/** Filters narrowing the feed beyond the date interval and the sort order. */
function activeFilterCount(filters: WorldFilters): number {
  return [filters.country, filters.ticker, filters.theme, filters.q, filters.bbox].filter(Boolean).length + filters.categories.length + filters.origins.length;
}

function toggle<T>(list: readonly T[], value: T, on: boolean): T[] {
  return on ? [...list.filter(item => item !== value), value] : list.filter(item => item !== value);
}

function WorldContent({ profile }: { profile: Profile }) {
  const app = useApp();
  const { tr, lang, sessionId, meta, feature } = app;
  const pKey = profileKey(app);
  const params = useSearchParams();
  const router = useRouter();
  const eventId = params.get('eventId');
  const countryIso3 = params.get('country');
  const runId = params.get('runId');

  // A change is merged into the latest selection, not into the values of the render that created the
  // callback: a late caller (a "Brief me" that just answered) must not undo a newer selection.
  const selection = useRef<WorldSelection>({ eventId, country: countryIso3, runId });
  useLayoutEffect(() => { selection.current = { eventId, country: countryIso3, runId }; }, [eventId, countryIso3, runId]);
  const navigate = useCallback((patch: WorldSelectionPatch) => {
    const next = mergeSelection(selection.current, patch);
    // Kept until the URL catches up, so two changes in a row build on each other.
    selection.current = next;
    const text = selectionQuery(next);
    router.replace(`/world-explorer/${text ? `?${text}` : ''}`, { scroll: false });
  }, [router]);
  // A brief belongs to one event: selecting another event drops it unless the caller keeps it.
  const selectEvent = useCallback((id: string, keepRun = false) => {
    navigate(eventSelectionPatch(selection.current, id, keepRun));
  }, [navigate]);
  const selectCountry = useCallback((iso3: string) => navigate({ country: iso3 }), [navigate]);

  // ----- layers -----
  const layers = useQuery<WorldLayersResponse>(sessionId && meta ? `world-layers|${sessionId}|${meta.dataVersion}` : null,
    signal => getApiClient().worldLayers(signal));
  const layerItems: WorldLayer[] | null = layers.data?.items ?? null;
  const layerCoverage = layerItems?.find(layer => layer.layerId === 'events')?.coverage ?? null;
  const [layersOn, setLayersOn] = useState<Record<LayerId, boolean>>({ events: true, exposure: true, facilities: false, hazards: false, airports: false });
  const layerStates = useMemo(() => Object.fromEntries(LAYER_IDS.map(id => {
    const state = layerState(id, layerItems, feature);
    // Without a layer list, the two core layers follow their own endpoints (feed, exposure).
    if (!layerItems && !layers.loading && state.reason === 'not_listed' && (id === 'events' || id === 'exposure')) {
      return [id, { ...state, enabled: true, reason: null }];
    }
    return [id, state];
  })) as Record<LayerId, ReturnType<typeof layerState>>, [layerItems, layers.loading, feature]);
  const isOn = (id: LayerId) => layersOn[id] && layerStates[id].enabled;

  // ----- filters: initialised from the dataset coverage once the layer list has answered -----
  const [draft, setDraft] = useState<WorldFilters>(EMPTY_FILTERS);
  const [applied, setApplied] = useState<WorldFilters | null>(null);
  const [coverage, setCoverage] = useState<Period | null>(null);
  const [formIssue, setFormIssue] = useState<FormIssue | null>(null);
  // Default view: only events with a documented link to this portfolio (review §4.6); untick to see all.
  const [relevantOnly, setRelevantOnly] = useState(true);
  const [mode, setMode] = useState<WorldMode>('portfolio');
  const [area, setArea] = useState('');
  const changeMode = (next: WorldMode) => {
    const preset = WORLD_MODES.find(item => item.id === next)!;
    setMode(next);
    setRelevantOnly(next === 'portfolio');
    setLayersOn(Object.fromEntries(LAYER_IDS.map(id => [id, preset.layers.includes(id)])) as Record<LayerId, boolean>);
    setDraft(value => ({ ...value, categories: [...preset.categories] }));
    setApplied(value => value && ({ ...value, categories: [...preset.categories] }));
    setPicked(null);
  };
  const changeArea = (id: string) => {
    const box = GEOGRAPHIC_AREAS.find(item => item.id === id)?.bbox ?? '';
    setArea(id);
    setDraft(value => ({ ...value, bbox: box, country: '' }));
    setApplied(value => value && ({ ...value, bbox: box, country: '' }));
    navigate({ country: null });
  };
  const queryViewport = useCallback((bbox: string) => {
    setArea('');
    setDraft(value => ({ ...value, bbox, country: '' }));
    setApplied(value => value && ({ ...value, bbox, country: '' }));
    navigate({ country: null });
  }, [navigate]);
  useEffect(() => {
    if (applied !== null || layers.loading) return;
    const initial = layerCoverage ? { ...EMPTY_FILTERS, ...defaultRange(layerCoverage) } : EMPTY_FILTERS;
    if (layerCoverage) setCoverage(layerCoverage);
    setDraft(initial);
    setApplied(initial);
  }, [applied, layers.loading, layerCoverage]);
  // No coverage from the layer list: the first page used the API default interval; adopt the coverage it reports.
  useEffect(() => {
    if (!applied || applied.from || !coverage) return;
    const range = defaultRange(coverage);
    setApplied(current => (current && !current.from ? { ...current, ...range } : current));
    setDraft(current => (current.from ? current : { ...current, ...range }));
  }, [applied, coverage]);

  // ----- feed: first page per filter set, further pages by cursor -----
  const feedKey = applied && pKey ? `${pKey}|${filtersKey(applied, profile.profileId)}` : null;
  const [feed, setFeed] = useState<FeedState>(EMPTY_FEED);
  const [nonce, setNonce] = useState(0);
  const liveKey = useRef<string | null>(null);
  useEffect(() => {
    liveKey.current = feedKey;
    if (!feedKey || !applied) return undefined;
    const controller = new AbortController();
    setFeed(previous => ({ ...previous, loading: true, loadingMore: false, error: null, moreError: null }));
    getApiClient().worldEvents(buildEventsQuery(applied, profile.profileId), controller.signal).then(
      page => {
        if (controller.signal.aborted) return;
        setFeed({
          key: feedKey, profileId: profile.profileId, items: page.items, nextCursor: page.nextCursor, total: page.total,
          dataVersion: page.dataVersion, loadedAt: new Date().toISOString(), loading: false, loadingMore: false, error: null, moreError: null,
        });
        setCoverage(page.coverage);
      },
      error => {
        if (controller.signal.aborted || isAbort(error)) return;
        // The previously loaded feed is kept (and labelled) rather than erased by a failed lookup.
        setFeed(previous => ({ ...previous, loading: false, error: asApiError(error) }));
      },
    );
    return () => controller.abort();
    // feedKey captures the applied filters and the profile version.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [feedKey, nonce]);

  const loadMore = async () => {
    if (!applied || !feed.nextCursor || feed.loadingMore || feed.key !== feedKey) return;
    const startedFor = feedKey;
    setFeed(previous => ({ ...previous, loadingMore: true, moreError: null }));
    try {
      const page = await getApiClient().worldEvents(buildEventsQuery(applied, profile.profileId, feed.nextCursor));
      if (liveKey.current !== startedFor) return;
      setFeed(previous => (previous.key !== startedFor ? previous : {
        ...previous, items: mergeEventPages(previous.items, page.items), nextCursor: page.nextCursor, total: page.total, loadingMore: false,
      }));
    } catch (error) {
      if (liveKey.current !== startedFor) return;
      setFeed(previous => ({ ...previous, loadingMore: false, moreError: asApiError(error) }));
    }
  };

  const current = feed.key === feedKey;
  const sameProfile = feed.profileId === profile.profileId;
  // Events of other filters are shown only next to the error that explains why they are still there.
  const keptAfterFailure = !current && sameProfile && feed.error !== null && !feed.loading && feed.items.length > 0;
  const loaded = useMemo(() => (sameProfile && (current || keptAfterFailure) ? feed.items : []), [sameProfile, current, keptAfterFailure, feed.items]);
  const relevanceKnown = loaded.some(event => event.portfolioRelevant !== undefined);
  const visible = useMemo(() => visibleEvents(loaded, relevantOnly && relevanceKnown), [loaded, relevantOnly, relevanceKnown]);
  const relevantCount = loaded.filter(event => event.portfolioRelevant === true).length;

  // ----- exposure and optional layers -----
  const exposure = useQuery<WorldExposureResponse>(pKey ? `world-exposure|${pKey}` : null,
    signal => getApiClient().worldExposure(profile.profileId, signal));
  const exposureByIso3 = useMemo(() => {
    if (!exposure.data) return null;
    return new Map(exposure.data.items.filter(row => isKnownIso3(row.countryIso3)).map(row => [row.countryIso3, row.weightPct]));
  }, [exposure.data]);

  const facilitiesOn = isOn('facilities');
  const hazardsOn = isOn('hazards');
  // The card, its table and the globe legend name what the API says is loaded ("Earthquakes (USGS)"), not a wider category.
  const hazardsTitle = layerStates.hazards.layer ? tr(layerStates.hazards.layer.title) : labelOf(WORLD_LAYER, 'hazards', lang);
  const appliedCountry = applied?.country ?? '';
  const facilities = useQuery<FacilitiesResponse>(facilitiesOn && sessionId && meta ? `world-facilities|${sessionId}|${meta.dataVersion}|${appliedCountry}|${applied?.bbox ?? ''}` : null,
    signal => getApiClient().worldFacilities({ limit: EXTRA_LAYER_LIMIT, ...(appliedCountry ? { country: [appliedCountry] } : {}), ...(applied?.bbox ? { bbox: applied.bbox } : {}) }, signal));
  const hazards = useQuery<HazardsResponse>(hazardsOn && sessionId && meta && applied ? `world-hazards|${sessionId}|${meta.dataVersion}|${applied.from}|${applied.to}|${applied.bbox ?? ''}` : null,
    signal => getApiClient().worldHazards({ limit: EXTRA_LAYER_LIMIT, ...(applied?.from && applied.to ? { from: applied.from, to: applied.to } : {}), ...(applied?.bbox ? { bbox: applied.bbox } : {}) }, signal));

  const airportsOn = isOn('airports');
  const airports = useQuery<AirportsResponse>(airportsOn && sessionId ? `world-airports|${sessionId}|${countryIso3 ?? ''}` : null,
    signal => getApiClient().worldAirports({ limit: 2000, ...(countryIso3 ? { country: [countryIso3] } : {}) }, signal));
  const airportRows = useMemo(() => (airports.data?.items ?? []).filter(row => !applied?.bbox || insideBbox(row.lat, row.lon, applied.bbox)), [airports.data, applied?.bbox]);
  const airportPins = useMemo(() => spatialReferencePins(airportRows, MAX_PINS), [airportRows]);

  // ----- pins (capped separately from the feed) -----
  const eventsOn = isOn('events');
  const [observationPins, setObservationPins] = useState<GlobePin[]>([]);
  const [observationId, setObservationId] = useState<string | null>(null);
  const [observationGeometry, setObservationGeometry] = useState<Record<string, unknown> | null>(null);
  useEffect(() => { setObservationId(null); }, [mode, applied?.bbox, countryIso3, appliedCountry]);
  const pinSelection = useMemo(() => thinPins(visible, MAX_PINS, eventId), [visible, eventId]);
  const facilityPins = useMemo(() => (facilities.data?.items ?? []).slice(0, MAX_PINS), [facilities.data]);
  const hazardPins = useMemo(() => (hazards.data?.items ?? []).slice(0, MAX_PINS), [hazards.data]);
  const pins = useMemo<GlobePin[]>(() => [
    ...observationPins,
    ...(eventsOn ? pinSelection.pins.map(event => ({
      id: event.eventId, kind: 'event' as const, lat: event.location.lat, lng: event.location.lon, label: event.title,
      countryLevel: event.location.precision === 'country', weight: event.importance,
      category: event.category, related: event.relatedCountries,
    })) : []),
    ...(facilitiesOn ? facilityPins.map(facility => ({
      id: `facility:${facility.facilityId}`, kind: 'facility' as const, lat: facility.lat, lng: facility.lon, label: facility.name, countryLevel: false, weight: 0.2,
    })) : []),
    ...(hazardsOn ? hazardPins.map(hazard => ({
      id: `hazard:${hazard.hazardId}`, kind: 'hazard' as const, lat: hazard.lat, lng: hazard.lon, label: hazard.title, countryLevel: false, weight: 0.2,
      ...(typeof hazard.magnitude === 'number' ? { magnitude: hazard.magnitude } : {}),
    })) : []),
    ...(airportsOn ? airportPins.map(airport => ({
      id: airport.airportId, kind: 'airport' as const, lat: airport.lat, lng: airport.lon,
      label: `${airport.ident} · ${airport.name}`, countryLevel: false, weight: 0.15,
    })) : []),
  ], [observationPins, eventsOn, facilitiesOn, hazardsOn, airportsOn, pinSelection, facilityPins, hazardPins, airportPins]);

  const selectedEvent = useMemo(() => (eventId ? loaded.find(event => event.eventId === eventId) ?? null : null), [eventId, loaded]);
  const openDetails = useCallback(() => {
    document.querySelector('.world-panels')?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'start' });
  }, []);
  const [picked, setPicked] = useState<GlobePin | null>(null);
  const onPin = useCallback((pin: GlobePin) => {
    if (pin.kind === 'observation') { setObservationId(pin.id); setPicked(null); }
    else if (pin.kind === 'event') { setPicked(null); setObservationId(null); selectEvent(pin.id); } else setPicked(pin);
  }, [selectEvent]);

  // ----- filter form -----
  const dirty = applied !== null && filtersKey(draft, null) !== filtersKey(applied, null);
  const apply = (event: FormEvent) => {
    event.preventDefault();
    const next: WorldFilters = { ...draft, country: draft.country.trim().toUpperCase(), ticker: draft.ticker.trim().toUpperCase(), q: draft.q.trim() };
    if (next.bbox && !validBbox(next.bbox)) { setFormIssue('bbox'); return; }
    if (Boolean(next.from) !== Boolean(next.to)) { setFormIssue('partial'); return; }
    if (next.from && next.to) {
      const issue = rangeIssue({ from: next.from, to: next.to }, coverage);
      if (issue) { setFormIssue(issue); return; }
    }
    if (next.country && !/^[A-Z]{3}$/.test(next.country)) { setFormIssue('country'); return; }
    setFormIssue(null);
    setDraft(next);
    setApplied(next);
  };
  const fitRange = () => {
    if (!draft.from || !draft.to) return;
    const fitted = clampRange({ from: draft.from, to: draft.to }, coverage);
    setDraft(value => ({ ...value, from: fitted.from, to: fitted.to }));
    setFormIssue(null);
  };
  const reset = () => {
    const base = coverage ? { ...EMPTY_FILTERS, ...defaultRange(coverage) } : EMPTY_FILTERS;
    setDraft(base); setApplied(base); setFormIssue(null); setRelevantOnly(true); setArea(''); setMode('portfolio');
    setLayersOn({ events: true, exposure: true, facilities: false, hazards: false, airports: false });
  };
  const countryOptions = useMemo(() => {
    const codes = new Set<string>();
    for (const row of exposure.data?.items ?? []) if (isKnownIso3(row.countryIso3)) codes.add(row.countryIso3);
    for (const event of loaded) if (event.location.countryIso3) codes.add(event.location.countryIso3);
    return [...codes].sort();
  }, [exposure.data, loaded]);

  const exposureScope = useMemo<FactScope | null>(() => (exposure.data ? {
    kind: 'local',
    label: { en: `Country exposure of ${profile.name}, computed by code.`, fr: `Exposition par pays de ${profile.name}, calculée par le code.` },
    facts: exposure.data.facts,
  } : null), [exposure.data, profile.name]);

  return (
    <>
      <PageHeader tour="world-header" title={tr({ en: `World Explorer · ${profile.name}`, fr: `Explorateur mondial · ${profile.name}` })}>
        <p className="page-sub">{tr({ en: 'Explore source observations, geographic references and portfolio relevance. Each source and relationship retains its coverage and evidence limits.', fr: 'Explorez observations sourcées, références géographiques et pertinence pour le portefeuille. Chaque source et relation conserve ses limites de couverture et de preuve.' })}</p>
      </PageHeader>

      <WorldNavigation mode={mode} onMode={changeMode} onCountry={selectCountry} area={area} onArea={changeArea}
        bbox={draft.bbox ?? ''} onBbox={bbox => { setArea(''); setDraft(value => ({ ...value, bbox })); }} />
      {!layers.loading && WORLD_MODES.find(item => item.id === mode)!.layers.filter(id => !layerStates[id as LayerId]?.enabled).map(id =>
        <p key={id} className="small" role="status">{labelOf(WORLD_LAYER, id, lang)}: {tr(LAYER_REASON[layerStates[id as LayerId]?.reason ?? 'not_listed'])}</p>)}
      <WorldGlobe pins={pins} selectedId={observationId ?? eventId} selectedGeometry={observationGeometry} selectedCountry={countryIso3 && isKnownIso3(countryIso3) ? countryIso3 : null}
        selectedEvent={selectedEvent} exposure={isOn('exposure') ? exposureByIso3 : null} exposureRows={exposure.data?.items ?? []}
        counts={{ shown: visible.length, total: feed.total, linked: relevantCount }} showHazards={hazardsOn} hazardsLabel={hazardsTitle}
        onPin={onPin} onCountry={selectCountry} onOpenDetails={openDetails} area={GEOGRAPHIC_AREAS.find(item => item.id === area) ?? null} onViewport={queryViewport} />

      <div className="world-controls">
        <Card id="filters" section={tr({ en: 'Filters', fr: 'Filtres' })} tour="world-filters" title={tr({ en: 'Filters', fr: 'Filtres' })}>
          <div className="checks">
            <label>
              <input type="checkbox" checked={relevantOnly && relevanceKnown} disabled={!relevanceKnown} onChange={e => setRelevantOnly(e.target.checked)} />
              {tr({ en: `Only events matching ${profile.name}’s portfolio`, fr: `Seulement les événements correspondant au portefeuille de ${profile.name}` })}
            </label>
          </div>
          <p className="small muted">
            {relevanceKnown
              ? tr({ en: 'A held ticker is named in the event, or the event’s country has weight in the portfolio.', fr: 'Un symbole détenu est nommé dans l’événement, ou le pays de l’événement a un poids dans le portefeuille.' })
              : tr({ en: 'Not available yet: the API has not returned a portfolio match for the loaded events.', fr: 'Pas encore disponible : l’API n’a pas renvoyé de correspondance avec le portefeuille pour les événements chargés.' })}
          </p>
          <details className="filters-fold">
            <summary>
              {tr({ en: 'Dates, countries, categories and sources', fr: 'Dates, pays, catégories et sources' })}
              {applied?.from && applied.to && <span className="small muted"> · {fmtDate(applied.from, lang)} → {fmtDate(applied.to, lang)}</span>}
              {applied && activeFilterCount(applied) > 0 && <span className="small muted"> · {tr({ en: `${activeFilterCount(applied)} filter(s) applied`, fr: `${activeFilterCount(applied)} filtre(s) appliqué(s)` })}</span>}
            </summary>
          <form onSubmit={apply} noValidate>
            <div className="form-grid">
              <div className="field">
                <label htmlFor="world-from">{tr({ en: 'From', fr: 'Du' })}</label>
                <input id="world-from" type="date" value={draft.from} min={coverage?.start} max={coverage?.end}
                  onChange={e => setDraft(value => ({ ...value, from: e.target.value }))} aria-describedby="world-range-hint" />
              </div>
              <div className="field">
                <label htmlFor="world-to">{tr({ en: 'To', fr: 'Au' })}</label>
                <input id="world-to" type="date" value={draft.to} min={coverage?.start} max={coverage?.end}
                  onChange={e => setDraft(value => ({ ...value, to: e.target.value }))} aria-describedby="world-range-hint" />
              </div>
              <div className="field">
                <label htmlFor="world-country">{tr({ en: 'Country (ISO code)', fr: 'Pays (code ISO)' })}</label>
                <input id="world-country" type="text" list="world-country-options" maxLength={3} autoComplete="off" value={draft.country}
                  onChange={e => setDraft(value => ({ ...value, country: e.target.value.toUpperCase() }))} placeholder="CAN" />
                <datalist id="world-country-options">
                  {countryOptions.map(code => <option key={code} value={code}>{countryLabel(code, lang)}</option>)}
                </datalist>
              </div>
              <div className="field">
                <label htmlFor="world-ticker">{tr({ en: 'Ticker named in the event', fr: 'Symbole nommé dans l’événement' })}</label>
                <input id="world-ticker" type="text" list="world-ticker-options" autoComplete="off" value={draft.ticker}
                  onChange={e => setDraft(value => ({ ...value, ticker: e.target.value.toUpperCase() }))} />
                <datalist id="world-ticker-options">
                  {profile.portfolio.positions.map(position => <option key={position.ticker} value={position.ticker} />)}
                </datalist>
              </div>
              <div className="field">
                <label htmlFor="world-theme">{tr({ en: 'Theme', fr: 'Thème' })}</label>
                <select id="world-theme" value={draft.theme} onChange={e => setDraft(value => ({ ...value, theme: e.target.value }))}>
                  <option value="">{tr({ en: 'All themes', fr: 'Tous les thèmes' })}</option>
                  {THEME_TAGS.map(theme => <option key={theme} value={theme}>{labelOf(THEME_TAG, theme, lang)}</option>)}
                </select>
              </div>
              <div className="field">
                <label htmlFor="world-q">{tr({ en: 'Text in title or publisher', fr: 'Texte du titre ou de l’éditeur' })}</label>
                <input id="world-q" type="search" value={draft.q} maxLength={120} onChange={e => setDraft(value => ({ ...value, q: e.target.value }))} />
              </div>
              <div className="field">
                <label htmlFor="world-sort">{tr({ en: 'Sort by', fr: 'Trier par' })}</label>
                <select id="world-sort" value={draft.sort} onChange={e => setDraft(value => ({ ...value, sort: e.target.value === 'date' ? 'date' : 'importance' }))}>
                  <option value="importance">{tr({ en: 'Ranking score', fr: 'Score de classement' })}</option>
                  <option value="date">{tr({ en: 'Date (most recent first)', fr: 'Date (plus récent d’abord)' })}</option>
                </select>
              </div>
            </div>
            <p id="world-range-hint" className="hint small muted" style={{ marginTop: 6 }}>
              {coverage
                ? <>{tr({ en: 'Dataset coverage', fr: 'Couverture du jeu de données' })}: {fmtDate(coverage.start, lang)} → {fmtDate(coverage.end, lang)}. </>
                : <>{tr({ en: 'Dataset coverage not known yet; without dates the API uses the last 30 days of its events dataset.', fr: 'Couverture du jeu de données pas encore connue ; sans dates, l’API utilise les 30 derniers jours de son jeu d’événements.' })} </>}
              {tr({ en: `${MAX_RANGE_DAYS} days at most.`, fr: `${MAX_RANGE_DAYS} jours au plus.` })}
            </p>

            <div className="filter-sets">
              <fieldset>
                <legend>{tr({ en: 'Categories (none ticked = all)', fr: 'Catégories (aucune cochée = toutes)' })}</legend>
                <div className="checks">
                  {EVENT_CATEGORIES.map(category => (
                    <label key={category}>
                      <input type="checkbox" checked={draft.categories.includes(category)}
                        onChange={e => setDraft(value => ({ ...value, categories: toggle<EventCategory>(value.categories, category, e.target.checked) }))} />
                      {labelOf(EVENT_CATEGORY, category, lang)}
                    </label>
                  ))}
                </div>
              </fieldset>
              <fieldset>
                <legend>{tr({ en: 'Source origin (none ticked = all)', fr: 'Origine de la source (aucune cochée = toutes)' })}</legend>
                <div className="checks">
                  {EVENT_ORIGINS.map(origin => (
                    <label key={origin}>
                      <input type="checkbox" checked={draft.origins.includes(origin)}
                        onChange={e => setDraft(value => ({ ...value, origins: toggle<WorldEvent['origin']>(value.origins, origin, e.target.checked) }))} />
                      {labelOf(EVENT_ORIGIN, origin, lang)}
                    </label>
                  ))}
                </div>
              </fieldset>
            </div>

            {formIssue && (
              <div className="error-summary" role="alert" style={{ marginTop: 12 }}>
                <p className="small">{tr(FORM_ISSUE[formIssue])}</p>
                {(formIssue === 'too_long' || formIssue === 'order' || formIssue === 'outside_coverage') && draft.from && draft.to && (
                  <button type="button" className="btn ghost btn-sm" onClick={fitRange}>
                    {tr({ en: 'Fit the interval to the limit and the coverage', fr: 'Ajuster l’intervalle à la limite et à la couverture' })}
                  </button>
                )}
              </div>
            )}
            <div className="row-actions">
              <button type="submit" className="btn" disabled={applied === null}>{tr({ en: 'Apply filters', fr: 'Appliquer les filtres' })}</button>
              <button type="button" className="btn ghost" onClick={reset} disabled={applied === null}>{tr({ en: 'Reset to the dataset coverage', fr: 'Revenir à la couverture du jeu de données' })}</button>
              {dirty && <span className="small muted" role="status">{tr({ en: 'Filters changed; apply them to update the feed.', fr: 'Filtres modifiés ; appliquez-les pour mettre le fil à jour.' })}</span>}
            </div>
          </form>
          </details>
        </Card>
        <div className="world-layers">
          {picked && (
            <p className="small" role="status">
              <strong>{picked.kind === 'airport' ? tr({ en: 'Airport reference', fr: 'Référence aéroportuaire' }) : picked.kind === 'facility' ? tr({ en: 'Facility', fr: 'Installation' }) : tr({ en: 'Hazard', fr: 'Aléa' })}:</strong> {picked.label}.{' '}
              {tr({ en: 'Its details are in the table below.', fr: 'Ses détails sont dans le tableau ci-dessous.' })}
            </p>
          )}
          <Card id="layers" title={tr({ en: 'Layers', fr: 'Couches' })}>
            {layers.loading && <Loading />}
            {layers.error && (
              <ErrorState error={layers.error} onRetry={layers.reload}
                title={tr({ en: 'The layer list could not be loaded. Optional layers stay off.', fr: 'La liste des couches n’a pas pu être chargée. Les couches facultatives restent désactivées.' })} />
            )}
            <ul className="layer-list">
              {LAYER_IDS.map(id => {
                const state = layerStates[id];
                const layer = state.layer;
                return (
                  <li key={id}>
                    <label className="layer-toggle">
                      <input type="checkbox" checked={isOn(id)} disabled={!state.enabled} aria-describedby={`layer-${id}-note`}
                        onChange={e => setLayersOn(value => ({ ...value, [id]: e.target.checked }))} />
                      <span>{layer ? tr(layer.title) : labelOf(WORLD_LAYER, id, lang)}</span>
                    </label>
                    <p id={`layer-${id}-note`} className="small muted">
                      {layers.loading ? tr({ en: 'Checking source availability…', fr: 'Vérification des sources…' }) : state.reason && <strong>{tr(LAYER_REASON[state.reason])} </strong>}
                      {layer && layer.count !== null && <>{fmtNumber(layer.count, lang, 0)} {tr({ en: 'item(s)', fr: 'élément(s)' })}. </>}
                      {layer?.coverage && <>{fmtDate(layer.coverage.start, lang)} → {fmtDate(layer.coverage.end, lang)}. </>}
                      {layer && layer.datasetIds.length > 0 && (
                        <>{tr({ en: 'Data', fr: 'Données' })}: {layer.datasetIds.map((datasetId, i) => (
                          <span key={datasetId}>{i > 0 && ', '}<Link className="mono" href={`/sources/?datasetId=${encodeURIComponent(datasetId)}`}>{datasetId}</Link></span>
                        ))}</>
                      )}
                    </p>
                  </li>
                );
              })}
            </ul>
          </Card>
        </div>
      </div>

      {mode !== 'portfolio' && <WorldObservations mode={mode} bbox={applied?.bbox ?? ''} country={countryIso3 && isKnownIso3(countryIso3) ? countryIso3 : appliedCountry}
        q={applied?.q ?? ''} from={applied?.from ?? ''} to={applied?.to ?? ''} selectedId={observationId} onPins={setObservationPins} onSelect={setObservationId} onGeometry={setObservationGeometry} />}
      {mode !== 'aviation' && mode !== 'infrastructure' && <Card id="feed" className="world-feed" section={tr({ en: 'Feed', fr: 'Fil' })} tour="world-feed" title={tr({ en: 'Event feed', fr: 'Fil d’événements' })}
        actions={<button type="button" className="btn ghost btn-sm" onClick={() => setNonce(n => n + 1)} disabled={feed.loading || applied === null}>{tr({ en: 'Reload', fr: 'Recharger' })}</button>}>
        <div role="status" aria-live="polite" className="small feed-counts">
          {(current || keptAfterFailure) && feed.total !== null && (
            <p>
              {tr({
                en: `${visible.length} of ${feed.total} events`,
                fr: `${visible.length} sur ${feed.total} événements`,
              })}
              {relevantOnly && relevanceKnown && <>{tr({ en: `, ${relevantCount} linked to the portfolio`, fr: `, ${relevantCount} liés au portefeuille` })}</>}
            </p>
          )}
        </div>
        {(layers.loading || applied === null || (feed.loading && !keptAfterFailure)) && <Loading label={tr({ en: 'Loading events…', fr: 'Chargement des événements…' })} />}
        {feed.error && !feed.loading && (
          <ErrorState error={feed.error} onRetry={() => setNonce(n => n + 1)}
            title={tr({ en: 'The events could not be loaded for these filters.', fr: 'Les événements n’ont pas pu être chargés pour ces filtres.' })}>
            {feed.items.length > 0 && sameProfile && feed.loadedAt && (
              <p className="small">
                {current
                  ? tr({ en: `The list below is the copy loaded at ${fmtDateTime(feed.loadedAt, 'en')}; it was not refreshed.`, fr: `La liste ci-dessous est la copie chargée le ${fmtDateTime(feed.loadedAt, 'fr')} ; elle n’a pas été actualisée.` })
                  : tr({ en: `The list below was loaded at ${fmtDateTime(feed.loadedAt, 'en')} for the previous filters, not for the filters above.`, fr: `La liste ci-dessous a été chargée le ${fmtDateTime(feed.loadedAt, 'fr')} pour les filtres précédents, pas pour les filtres ci-dessus.` })}
              </p>
            )}
          </ErrorState>
        )}
        {applied !== null && !layers.loading && current && feed.total !== null && !feed.loading && !feed.error && loaded.length === 0 && (
          <Empty>{tr({ en: 'No event matches these filters in the loaded dataset. Widen the interval or remove a filter.', fr: 'Aucun événement ne correspond à ces filtres dans le jeu de données chargé. Élargissez l’intervalle ou retirez un filtre.' })}</Empty>
        )}
        {loaded.length > 0 && visible.length === 0 && (
          <Empty>{tr({ en: 'None of the loaded events matches this portfolio. Load more events or untick the portfolio filter.', fr: 'Aucun des événements chargés ne correspond à ce portefeuille. Chargez plus d’événements ou décochez le filtre de portefeuille.' })}</Empty>
        )}
        {visible.length > 0 && (
          <ol className="feed-list" aria-label={tr({ en: 'Events, in the order returned by the API', fr: 'Événements, dans l’ordre renvoyé par l’API' })}>
            {visible.map(event => (
              <li key={event.eventId}>
                <button type="button" className="feed-item" aria-current={event.eventId === eventId ? 'true' : undefined} onClick={() => selectEvent(event.eventId)}>
                  <span className="feed-title" lang={sourceLang(event)}>{event.title}</span>
                  <EventLine event={event} />
                  <span className="block">
                    {event.portfolioRelevant === true && <span className="tag tag-strong">{tr({ en: 'Linked to the portfolio', fr: 'Lié au portefeuille' })}</span>}
                    {event.location.precision === 'country' && <span className="tag">{labelOf(LOCATION_PRECISION, 'country', lang)}</span>}
                    {event.sourceCount > 1 && <span className="tag">{event.sourceCount} {tr({ en: 'sources', fr: 'sources' })}</span>}
                  </span>
                </button>
              </li>
            ))}
          </ol>
        )}
        {current && feed.nextCursor && (
          <div className="row-actions">
            <button type="button" className="btn ghost" onClick={() => void loadMore()} disabled={feed.loadingMore}>
              {tr({ en: 'Load the next page', fr: 'Charger la page suivante' })}
            </button>
            {feed.total !== null && <span className="small muted">{tr({ en: `${Math.max(0, feed.total - feed.items.length)} more in the dataset for these filters.`, fr: `${Math.max(0, feed.total - feed.items.length)} de plus dans le jeu de données pour ces filtres.` })}</span>}
          </div>
        )}
        {feed.loadingMore && <Loading label={tr({ en: 'Loading the next page…', fr: 'Chargement de la page suivante…' })} />}
        {feed.moreError && (
          <ErrorState error={feed.moreError} onRetry={() => void loadMore()}
            title={tr({ en: 'The next page could not be loaded. The events already loaded stay listed.', fr: 'La page suivante n’a pas pu être chargée. Les événements déjà chargés restent listés.' })} />
        )}
      </Card>}

      {(eventId || countryIso3) && (
        <div className="world-panels">
          {eventId && (
            <EventPanel eventId={eventId} profile={profile} runId={runId}
              onSelectEvent={id => selectEvent(id, true)} onSelectCountry={selectCountry}
              onRun={id => navigate({ runId: id })} onClose={() => navigate({ eventId: null, runId: null })} />
          )}
          {countryIso3 && isKnownIso3(countryIso3) && (
            <CountryPanel iso3={countryIso3} profile={profile} from={applied?.from ?? ''} to={applied?.to ?? ''}
              onSelectEvent={id => selectEvent(id)} onClose={() => navigate({ country: null })} />
          )}
          {countryIso3 && !isKnownIso3(countryIso3) && (
            // The no-listing-country bucket (ZZZ) and malformed codes are never requested as a country.
            <Card title={tr({ en: 'Country', fr: 'Pays' })}
              actions={<button type="button" className="btn ghost btn-sm" onClick={() => navigate({ country: null })}>{tr({ en: 'Close country', fr: 'Fermer le pays' })}</button>}>
              <Unavailable title={tr({ en: 'This code is not a country, so there is no country panel for it.', fr: 'Ce code n’est pas un pays ; il n’a donc pas de panneau de pays.' })}>
                <span className="mono">{countryIso3.slice(0, 12)}</span>
              </Unavailable>
            </Card>
          )}
        </div>
      )}

      <Card id="exposure" title={tr({ en: `Portfolio weight by country — ${profile.name}`, fr: `Poids du portefeuille par pays — ${profile.name}` })}>
        {exposure.loading && <Loading />}
        {exposure.error && <ErrorState error={exposure.error} onRetry={exposure.reload}
          title={tr({ en: 'The country exposure could not be loaded. No weight is shown.', fr: 'L’exposition par pays n’a pas pu être chargée. Aucun poids n’est affiché.' })} />}
        {exposure.data && exposureScope && (
          <FactScopeProvider scope={exposureScope}>
            <p className="small">{tr(exposure.data.basisNote)}</p>
            {exposure.data.items.length === 0 ? (
              <Empty>{tr({ en: 'The API returned no country exposure for this portfolio.', fr: 'L’API n’a renvoyé aucune exposition par pays pour ce portefeuille.' })}</Empty>
            ) : (
              <div className="table-scroll" role="region" aria-label={tr({ en: 'Portfolio weight by country', fr: 'Poids du portefeuille par pays' })} tabIndex={0}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th scope="col">{tr({ en: 'Country', fr: 'Pays' })}</th>
                      <th scope="col" className="num-col">{tr({ en: 'Weight', fr: 'Poids' })}</th>
                      <th scope="col">{tr({ en: 'Basis', fr: 'Fondement' })}</th>
                      <th scope="col">{tr({ en: 'Holdings counted', fr: 'Positions comptées' })}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {exposure.data.items.map((row, i) => {
                      const residual = isResidualExposure(row, isKnownIso3);
                      const factId = exposureFactId(exposure.data?.facts ?? {}, row.countryIso3);
                      return (
                        <tr key={`${row.countryIso3}-${i}`} className={residual ? 'row-residual' : ''}>
                          <th scope="row">
                            {residual ? (
                              <>
                                {row.countryIso3 === NO_LISTING_COUNTRY
                                  ? tr({ en: 'No listing country (crypto, cash, unknown)', fr: 'Sans pays de cotation (crypto, liquidités, inconnu)' })
                                  : tr({ en: 'Unknown or not attributed to a country', fr: 'Inconnu ou non attribué à un pays' })}
                                <span className="block small muted">{tr({ en: 'Returned as', fr: 'Renvoyé sous' })} <span className="mono">{row.countryIso3}</span>. {tr({ en: 'Kept as its own row; not drawn on the globe and not reassigned to a country.', fr: 'Conservé sur sa propre ligne ; non tracé sur le globe et non réattribué à un pays.' })}</span>
                              </>
                            ) : (
                              <button type="button" className="linklike" onClick={() => selectCountry(row.countryIso3)}>{countryLabel(row.countryIso3, lang)}</button>
                            )}
                          </th>
                          <td className="num-col">{factId ? <FactChip factId={factId} display={fmtPct(row.weightPct, lang)} /> : <span className="num">{fmtPct(row.weightPct, lang)}</span>}</td>
                          <td>{labelOf(EXPOSURE_BASIS, row.basis, lang)}</td>
                          <td className="small">
                            {row.holdings.length === 0 ? '—' : row.holdings.map(holding => (
                              <span key={holding.ticker} className="holding-pair"><span className="mono">{holding.ticker}</span> <span className="num">{fmtPct(holding.weightPct, lang)}</span></span>
                            ))}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
            <p className="small muted">{tr({ en: 'Rows are shown exactly as returned. Weight that could not be matched to a country (cash, crypto, the part of a fund without published holdings) stays in its own row and is never spread over other countries.', fr: 'Les lignes sont affichées exactement comme renvoyées. Le poids non rattaché à un pays (encaisse, crypto, part d’un fonds sans titres publiés) reste sur sa propre ligne et n’est jamais réparti sur d’autres pays.' })}</p>
            <LimitationList codes={exposure.data.limitations} />
          </FactScopeProvider>
        )}
      </Card>

      {facilitiesOn && (
        <Card id="facilities" title={tr({ en: 'Emissions facilities', fr: 'Installations émettrices' })}>
          {facilities.loading && <Loading />}
          {facilities.error && <ErrorState error={facilities.error} onRetry={facilities.reload} />}
          {facilities.data && (
            <>
              <p className="small">
                {tr({
                  en: `Showing ${facilities.data.items.length} of ${facilities.data.total} facilities (reporting year ${facilities.data.reportingYear})${appliedCountry ? `, country ${appliedCountry}` : ''}; ${Math.min(facilities.data.items.length, MAX_PINS)} drawn on the globe.`,
                  fr: `${facilities.data.items.length} installations affichées sur ${facilities.data.total} (année de déclaration ${facilities.data.reportingYear})${appliedCountry ? `, pays ${appliedCountry}` : ''} ; ${Math.min(facilities.data.items.length, MAX_PINS)} tracées sur le globe.`,
                })}
              </p>
              {facilities.data.items.length === 0 ? <Empty>{tr({ en: 'No facility was returned.', fr: 'Aucune installation n’a été renvoyée.' })}</Empty> : (
                <div className="table-scroll" role="region" aria-label={tr({ en: 'Emissions facilities', fr: 'Installations émettrices' })} tabIndex={0}>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th scope="col">{tr({ en: 'Facility', fr: 'Installation' })}</th>
                        <th scope="col">{tr({ en: 'Reporting company (registry)', fr: 'Société déclarante (registre)' })}</th>
                        <th scope="col">{tr({ en: 'Issuer match', fr: 'Émetteur associé' })}</th>
                        <th scope="col">{tr({ en: 'Year', fr: 'Année' })}</th>
                        <th scope="col" className="num-col">{tr({ en: 'Reported tonnes CO₂e', fr: 'Tonnes éq. CO₂ déclarées' })}</th>
                        <th scope="col">{tr({ en: 'Registry', fr: 'Registre' })}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {facilities.data.items.map(facility => (
                        <tr key={facility.facilityId}>
                          <th scope="row">{facility.name}<span className="block small muted">{countryLabel(facility.countryIso3, lang)}</span></th>
                          <td>{facility.operator}</td>
                          <td>
                            {facility.ticker ? <span className="mono">{facility.ticker}</span> : '—'}
                            <span className={`block small${facility.matchConfidence === 'probable' ? ' nee-reason' : ' muted'}`}>{labelOf(MATCH_CONFIDENCE, facility.matchConfidence, lang)}</span>
                          </td>
                          <td className="num">{facility.reportingYear}</td>
                          <td className="num-col num">{fmtNumber(facility.emissionsTco2e, lang, 0)}</td>
                          <td className="small"><ExternalLink href={facility.sourceUrl}>{labelOf(REGISTRY, facility.registry, lang)}</ExternalLink></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <p className="small muted">{tr({ en: 'Reported registry figures, not a score. A facility near an event, or matched to an issuer by name, is not proof of any impact on a holding.', fr: 'Chiffres déclarés au registre, pas un score. Une installation proche d’un événement, ou associée par son nom à un émetteur, ne prouve aucun impact sur une position.' })}</p>
              <p className="small muted">{tr({ en: `ECCC annual facility-reported emissions for ${facilities.data.reportingYear}; captured ${facilities.data.capturedAt ?? '—'}. Total excludes biomass CO2. Revisions and reporting-program coverage apply. This is current reference data independent of event dates; reporting-company names establish neither security identity nor ownership.`, fr: `Émissions annuelles déclarées au PDGES pour ${facilities.data.reportingYear}; capture : ${facilities.data.capturedAt ?? '—'}. Le total exclut le CO2 de biomasse. Données révisables et couverture limitée au programme. Référence actuelle indépendante des dates des événements; le nom de la société déclarante ne prouve ni identité boursière ni propriété.` })}</p>
              <p className="small"><ExternalLink href="https://open.canada.ca/en/open-government-licence-canada">{tr({ en: 'Source: ECCC GHGRP · Open Government Licence – Canada', fr: 'Source : PDGES ECCC · Licence du gouvernement ouvert – Canada' })}</ExternalLink></p>
              <LimitationList codes={facilities.data.limitations} />
            </>
          )}
        </Card>
      )}

      {airportsOn && <Card title={tr({ en: 'Airport reference', fr: 'Référence aéroportuaire' })}>
        {airports.loading && <Loading />}
        {airports.error && <ErrorState error={airports.error} onRetry={airports.reload} />}
        {airports.data && <>
          <p className="small muted">{tr({
            en: `OurAirports · ${airportRows.length} references in this area from ${airports.data.items.length} loaded of ${airports.data.total} matching country records; ${airportPins.length} spatially sampled pins. Captured ${airports.data.capturedAt}. Current static reference; independent of event dates. No aircraft movements, operating status, company relationship or financial impact is established.`,
            fr: `OurAirports · ${airportRows.length} références dans cette zone parmi ${airports.data.items.length} chargées sur ${airports.data.total} enregistrements du pays ; ${airportPins.length} épingles réparties dans l’espace. Capture : ${airports.data.capturedAt}. Référence statique actuelle, indépendante des dates des événements. Aucun mouvement aérien, état opérationnel, lien d’entreprise ou impact financier établi.`,
          })}</p>
          <p className="small"><ExternalLink href="https://github.com/davidmegginson/ourairports-data/blob/main/LICENSE">{tr({ en: 'OurAirports public-domain dedication', fr: 'OurAirports : dédicace au domaine public' })}</ExternalLink> · <ExternalLink href="https://datacatalog.worldbank.org/public-licenses">{tr({ en: 'Country-code crosswalk: World Bank, CC BY 4.0', fr: 'Correspondance des codes pays : Banque mondiale, CC BY 4.0' })}</ExternalLink></p>
          <div className="table-scroll" role="region" aria-label={tr({ en: 'Airport references', fr: 'Références aéroportuaires' })} tabIndex={0}>
            <table><thead><tr><th>{tr({ en: 'Airport', fr: 'Aéroport' })}</th><th>{tr({ en: 'Country', fr: 'Pays' })}</th><th>{tr({ en: 'Source coordinates', fr: 'Coordonnées de la source' })}</th></tr></thead>
            <tbody>{airportRows.map(row => <tr key={row.airportId}><th scope="row"><ExternalLink href={row.sourceUrl}>{row.ident} · {row.name}</ExternalLink></th><td>{row.countryIso3 ?? row.countryIso2 ?? '—'}</td><td className="num">{row.lat.toFixed(3)}, {row.lon.toFixed(3)}</td></tr>)}</tbody></table>
          </div>
        </>}
      </Card>}

      {hazardsOn && (
        <Card id="hazards" title={hazardsTitle}>
          {hazards.loading && <Loading />}
          {hazards.error && <ErrorState error={hazards.error} onRetry={hazards.reload} />}
          {hazards.data && (
            <>
              <p className="small">
                {tr({
                  en: `Showing ${hazards.data.items.length} of ${hazards.data.total} hazard records; ${Math.min(hazards.data.items.length, MAX_PINS)} drawn on the globe.`,
                  fr: `${hazards.data.items.length} enregistrements d’aléas affichés sur ${hazards.data.total} ; ${Math.min(hazards.data.items.length, MAX_PINS)} tracés sur le globe.`,
                })}
              </p>
              {hazards.data.items.length === 0 ? <Empty>{tr({ en: 'No hazard record was returned for this interval.', fr: 'Aucun enregistrement d’aléa n’a été renvoyé pour cet intervalle.' })}</Empty> : (
                <div className="table-scroll" role="region" aria-label={hazardsTitle} tabIndex={0}>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th scope="col">{tr({ en: 'Record', fr: 'Enregistrement' })}</th>
                        <th scope="col">{tr({ en: 'Type', fr: 'Type' })}</th>
                        <th scope="col">{tr({ en: 'Time', fr: 'Heure' })}</th>
                        <th scope="col" className="num-col">{tr({ en: 'Magnitude', fr: 'Magnitude' })}</th>
                        <th scope="col">{tr({ en: 'Source', fr: 'Source' })}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {hazards.data.items.map(hazard => (
                        <tr key={hazard.hazardId}>
                          <th scope="row">{hazard.title}</th>
                          <td>{labelOf(HAZARD_TYPE, hazard.type, lang)}</td>
                          <td className="small">{fmtDateTime(hazard.occurredAt, lang)}</td>
                          <td className="num-col num">{hazard.magnitude === null ? tr({ en: 'not stated', fr: 'non indiquée' }) : fmtNumber(hazard.magnitude, lang, 1)}</td>
                          <td className="small"><ExternalLink href={hazard.sourceUrl}>{labelOf(EVENT_ORIGIN, hazard.origin, lang)}</ExternalLink></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </Card>
      )}
    </>
  );
}
