'use client';
import Link from 'next/link';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { WorldObservation, WorldObservationsResponse } from '../../contracts/types';
import { getApiClient } from '../../api/index';
import type { WorldObservationsQuery } from '../../api/client';
import { asApiError, isAbort, type ApiRequestError } from '../../api/errors';
import { profileKey, useApp } from '../../state/app';
import { Card } from '../../components/common/Page';
import { Sheet } from '../../components/common/Sheet';
import { Empty, ErrorState, Loading } from '../../components/common/States';
import { ExternalLink } from '../../components/common/ExternalLink';
import { countryLabel } from '../../lib/geo';
import { fmtDateTime } from '../../lib/format';
import { FEED_PAGE_SIZE, OBSERVATION_OVERVIEW_LIMIT, WORLD_MODES, type ObservationMode, type WorldMode } from '../../lib/world';
import type { GlobePin } from './globeStyle';
import { PortfolioAssessment } from './PortfolioAssessment';

type ObservationState = {
  key: string | null; page: WorldObservationsResponse | null; loading: boolean; loadingMore: boolean;
  error: ApiRequestError | null; moreError: ApiRequestError | null; loadedAt: string | null;
};
const INITIAL: ObservationState = { key: null, page: null, loading: false, loadingMore: false, error: null, moreError: null, loadedAt: null };

/** Source records retain their provenance; assessments show the match evidence and coverage. */
export function WorldObservations({ mode, bbox, country, q, from, to, selectedId, onPins, onSelect, onGeometry }: {
  mode: WorldMode; bbox: string; country: string; q: string; from: string; to: string; selectedId: string | null;
  onPins: (pins: GlobePin[]) => void; onSelect: (id: string | null) => void;
  onGeometry: (geometry: Record<string, unknown> | null) => void;
}) {
  const app = useApp();
  const { tr, lang } = app;
  const scope = profileKey(app);
  const profileId = app.profile?.profileId;
  const [useDates, setUseDates] = useState(false);
  const [markersOn, setMarkersOn] = useState(true);
  const [state, setState] = useState<ObservationState>(INITIAL);
  const [nonce, setNonce] = useState(0);
  const [feedLimit, setFeedLimit] = useState(FEED_PAGE_SIZE);
  // Only news, macro or environment is sent: the API answers 422 for any other mode.
  const sourceMode: ObservationMode | undefined = mode === 'portfolio' || mode === 'overview' ? undefined : mode;
  const query = useMemo<WorldObservationsQuery>(() => ({
    ...(profileId ? { profileId } : {}),
    ...(sourceMode ? { mode: sourceMode } : {}), ...(bbox ? { bbox } : {}),
    ...(country ? { country: [country] } : {}), ...(q ? { q } : {}),
    ...(useDates && from && to ? { from, to } : {}),
    scope: 'providers', order: 'coverage', mapOnly: mode === 'overview', limit: 500,
  }), [profileId, sourceMode, mode, bbox, country, q, useDates, from, to]);
  const key = scope ? `${scope}|${JSON.stringify(query)}` : null;
  const liveKey = useRef(key);
  useEffect(() => {
    liveKey.current = key;
    if (!key) { setState(INITIAL); return; }
    const controller = new AbortController();
    setState(previous => previous.key === key
      ? { ...previous, loading: true, error: null, moreError: null }
      : { ...INITIAL, key, loading: true });
    getApiClient().worldObservations(query, controller.signal).then(
      page => { if (!controller.signal.aborted) setState({ key, page, loading: false, loadingMore: false, error: null, moreError: null, loadedAt: new Date().toISOString() }); },
      error => { if (!controller.signal.aborted && !isAbort(error)) setState(previous => ({ ...previous, loading: false, loadingMore: false, error: asApiError(error) })); },
    );
    return () => controller.abort();
  }, [key, query, nonce]);
  const page = state.key === key ? state.page : null;
  useEffect(() => { setFeedLimit(FEED_PAGE_SIZE); }, [key]);
  useEffect(() => {
    if (!key || !page?.nextCursor || page.items.length >= OBSERVATION_OVERVIEW_LIMIT || state.loading || state.error || state.moreError) return;
    const controller = new AbortController();
    const startedFor = key;
    setState(previous => ({ ...previous, loadingMore: true }));
    getApiClient().worldObservations({ ...query, cursor: page.nextCursor }, controller.signal).then(
      next => {
        if (controller.signal.aborted) return;
        setState(previous => {
          if (previous.key !== startedFor) return previous;
          const seen = new Set(previous.page?.items.map(row => row.id));
          return { ...previous, loadingMore: false, page: {
            ...next, items: [...(previous.page?.items ?? []), ...next.items.filter(row => !seen.has(row.id))],
          } };
        });
      },
      error => {
        if (controller.signal.aborted || isAbort(error)) return;
        setState(previous => previous.key === startedFor ? { ...previous, loadingMore: false, moreError: asApiError(error) } : previous);
      },
    );
    return () => controller.abort();
  }, [key, query, page?.nextCursor, page?.items.length, state.loading, state.error, state.moreError]);
  const pins = useMemo<GlobePin[]>(() => (markersOn ? page?.items ?? [] : []).flatMap(row => row.location ? [{
    id: `observation:${row.id}`, kind: 'observation' as const, lat: row.location.lat, lng: row.location.lon,
    label: row.title, countryLevel: row.location.precision === 'country', weight: .2, geometry: row.location.geometry ?? null,
    observation: row,
  }] : []).filter((pin, index) => index < OBSERVATION_OVERVIEW_LIMIT || pin.id === selectedId), [page, markersOn, selectedId]);
  useEffect(() => { onPins(pins); return () => onPins([]); }, [pins, onPins]);
  const loadMore = useCallback(async () => {
    if (!page?.nextCursor || state.loadingMore || state.loading) return;
    const startedFor = key;
    setState(previous => ({ ...previous, loadingMore: true, moreError: null }));
    try {
      const next = await getApiClient().worldObservations({ ...query, cursor: page.nextCursor });
      if (liveKey.current !== startedFor) return;
      setState(previous => {
        if (previous.key !== startedFor) return previous;
        const seen = new Set(previous.page?.items.map(row => row.id));
        return { ...previous, loadingMore: false, page: { ...next, items: [...(previous.page?.items ?? []), ...next.items.filter(row => !seen.has(row.id))] } };
      });
    } catch (error) {
      if (liveKey.current === startedFor) setState(previous => previous.key === startedFor ? { ...previous, loadingMore: false, moreError: asApiError(error) } : previous);
    }
  }, [page, key, query, state.loadingMore, state.loading]);
  const selected = page?.items.find(row => `observation:${row.id}` === selectedId);
  // Polygon-only records have no point coordinates. Keep their source geometry separate from pins.
  const selectedGeometry = selected?.geometry ?? null;
  useEffect(() => { onGeometry(selectedGeometry); return () => onGeometry(null); }, [selectedGeometry, onGeometry]);
  const title = WORLD_MODES.find(item => item.id === mode)!.title;
  const availability = sourceMode ? page?.modes.find(item => item.mode === sourceMode) : null;
  const sources = useMemo(() => {
    const records = new Map<string, { name: string; count: number }>();
    for (const row of page?.items ?? []) {
      const source = records.get(row.datasetId) ?? { name: row.source.name, count: 0 };
      source.count++;
      records.set(row.datasetId, source);
    }
    return [...records.entries()];
  }, [page]);
  return <Card id="world-observations" title={`${tr(title)} · ${tr({ en: 'source observations', fr: 'observations sourcées' })}`}
    actions={<button type="button" className="btn ghost btn-sm" onClick={() => setNonce(value => value + 1)} disabled={state.loading}>{tr({ en: 'Refresh observations', fr: 'Actualiser les observations' })}</button>}>
    <label className="small"><input type="checkbox" checked={useDates} onChange={event => setUseDates(event.target.checked)} />
      {' '}{tr({ en: 'Filter observations by the event date interval', fr: 'Filtrer les observations selon l’intervalle des événements' })}</label>
    <label className="small block"><input type="checkbox" checked={markersOn} onChange={event => setMarkersOn(event.target.checked)} />
      {' '}{tr({ en: 'Show source observation pins', fr: 'Afficher les épingles des observations sourcées' })}</label>
    <p className="small muted">{tr({ en: 'Provider captures use their own observation dates. Capture-only references have no verified event time or historical vintage. A displayed point or polygon anchor does not prove company exposure.', fr: 'Les captures utilisent leurs propres dates d’observation. Les références datées uniquement par collecte n’ont ni heure d’événement ni version historique vérifiées. Un point ou ancrage de polygone ne prouve aucune exposition d’entreprise.' })}</p>
    {state.loading && <Loading />}
    {state.error && <ErrorState error={state.error} onRetry={() => setNonce(value => value + 1)} />}
    {state.error && page && state.loadedAt && <p className="small" role="status">{tr({ en: `Refresh failed. Showing the retained copy loaded at ${state.loadedAt}.`, fr: `Actualisation échouée. Copie conservée, chargée le ${state.loadedAt}.` })}</p>}
    {availability && !availability.available && <p className="small" role="status">{availability.reason ?? tr({ en: 'No authorized capture is loaded for this mode.', fr: 'Aucune capture autorisée chargée pour ce mode.' })}</p>}
    {page && <>
      <p className="small" role="status">{tr({ en: `${page.items.length} of ${page.total} source records loaded from ${sources.length} datasets · ${pins.length} additional globe markers.`, fr: `${page.items.length} enregistrements chargés sur ${page.total}, issus de ${sources.length} jeux de données · ${pins.length} marqueurs supplémentaires sur le globe.` })}</p>
      {page.nextCursor && <p className="small muted">{tr({ en: 'The overview balances sources and locations so large registries do not hide smaller feeds. Choose a topic or region, or load more records below.', fr: 'L’aperçu équilibre les sources et les lieux pour que les grands registres ne masquent pas les petits flux. Choisissez un thème ou une région, ou chargez davantage d’enregistrements ci-dessous.' })}</p>}
      <details className="fold">
        <summary>{tr({ en: 'Explore the loaded sources', fr: 'Explorer les sources chargées' })}</summary>
        <ul className="small">{sources.map(([id, source]) => <li key={id}>
          <Link href={`/sources/?datasetId=${encodeURIComponent(id)}`}>{source.name}</Link> · {source.count} {tr({ en: 'records loaded', fr: 'enregistrements chargés' })}
        </li>)}</ul>
        {page.capturedAt && <p className="small muted">{tr({ en: 'Latest capture', fr: 'Dernière capture' })}: {fmtDateTime(page.capturedAt, lang)}</p>}
      </details>
      {!page.items.length && !state.loading && <Empty>{tr({ en: 'No loaded observation matches this mode and geographic query. Broaden the area or date filters; source coverage may be unavailable.', fr: 'Aucune observation chargée ne correspond au mode et à la zone. Élargissez la zone ou les dates ; les sources peuvent être indisponibles.' })}</Empty>}
      <Sheet open={Boolean(selected)} title={tr({ en: 'Source data details', fr: 'Détails de la donnée sourcée' })} origin={null} onClose={() => onSelect(null)}>
        {selected && <ObservationDetail observation={selected} />}
      </Sheet>
      <ol className="feed-list" aria-label={tr({ en: 'Source observations', fr: 'Observations sourcées' })}>
        {page.items.slice(0, feedLimit).map(row => <li key={row.id}><button type="button" className="feed-item" aria-haspopup="dialog" aria-current={`observation:${row.id}` === selectedId ? 'true' : undefined} onClick={() => onSelect(`observation:${row.id}`)}>
          <span className="feed-title">{row.title}</span><span className="small muted block">{row.source.name} · {row.timeBasis === 'reference_period' ? row.occurredAt.slice(0, 7) : fmtDateTime(row.occurredAt, lang)} · {row.countryIso3 ? countryLabel(row.countryIso3, lang) : tr({ en: 'country not stated', fr: 'pays non indiqué' })}</span>
          <span className="small muted block">{row.location?.precision ?? (row.geometry ? tr({ en: 'Source boundary · no point', fr: 'Limite de source · sans point' }) : tr({ en: 'No source coordinates', fr: 'Aucune coordonnée de source' }))} · {row.timeBasis}</span>
        </button></li>)}
      </ol>
      {page.items.length > feedLimit && <button className="btn ghost" type="button" onClick={() => setFeedLimit(value => value + FEED_PAGE_SIZE)}>{tr({ en: 'Show more loaded records', fr: 'Afficher plus d’enregistrements chargés' })}</button>}
      {page.nextCursor && page.items.length >= OBSERVATION_OVERVIEW_LIMIT && <button className="btn ghost" type="button" onClick={() => void loadMore()} disabled={state.loadingMore || state.loading}>{tr({ en: 'Load more source data', fr: 'Charger plus de données sourcées' })}</button>}
      {state.loadingMore && <Loading />}
      {state.moreError && <ErrorState error={state.moreError} onRetry={() => {
        if (page.items.length < OBSERVATION_OVERVIEW_LIMIT) setState(previous => ({ ...previous, moreError: null }));
        else void loadMore();
      }} />}
      {page.items.length > pins.length && markersOn && <p className="small muted">{tr({ en: 'Records without coordinates stay in the list. Reference markers are limited to 2,000 per view; selecting another record adds its marker. Narrow the topic or geographic area to inspect its coverage.', fr: 'Les enregistrements sans coordonnées restent dans la liste. Les marqueurs de référence sont limités à 2 000 par vue ; sélectionner un autre enregistrement ajoute son marqueur. Précisez le thème ou la zone pour examiner sa couverture.' })}</p>}
    </>}
  </Card>;
}

function ObservationDetail({ observation }: { observation: WorldObservation }) {
  const { tr, lang } = useApp();
  return <div className="world-observation-detail world-event-details">
    <h3>{observation.title}</h3>
    <p className="small">{observation.summary}</p>
    <PortfolioAssessment assessment={observation.assessment} />
    <details className="fold">
      <summary>{tr({ en: 'Source, dates and geographic precision', fr: 'Source, dates et précision géographique' })}</summary>
    <dl>
      <div className="kv"><dt className="k">{tr({ en: 'Original source', fr: 'Source originale' })}</dt><dd className="v"><ExternalLink href={observation.source.url}>{observation.source.name}</ExternalLink></dd></div>
      <div className="kv"><dt className="k">{tr({ en: 'Observed / time basis', fr: 'Observation / fondement temporel' })}</dt><dd className="v">{observation.timeBasis === 'reference_period' ? `${tr({ en: 'Reference month', fr: 'Mois de référence' })} ${observation.occurredAt.slice(0, 7)}` : fmtDateTime(observation.occurredAt, lang)} · {observation.timeBasis}</dd></div>
      <div className="kv"><dt className="k">{tr({ en: 'Publication', fr: 'Publication' })}</dt><dd className="v">{observation.publishedAt ? fmtDateTime(observation.publishedAt, lang) : tr({ en: 'Not stated', fr: 'Non indiquée' })}</dd></div>
      <div className="kv"><dt className="k">{tr({ en: 'Retrieved', fr: 'Collecté' })}</dt><dd className="v">{fmtDateTime(observation.retrievedAt, lang)}</dd></div>
      <div className="kv"><dt className="k">{tr({ en: 'Source geometry', fr: 'Géométrie de source' })}</dt><dd className="v">{observation.location ? `${observation.location.precision} · ${observation.location.lat}, ${observation.location.lon}` : observation.geometry ? tr({ en: 'Source boundary available on the globe; no point coordinates supplied.', fr: 'Limite de source disponible sur le globe ; aucune coordonnée de point fournie.' }) : tr({ en: 'No coordinates supplied; this record has no map pin.', fr: 'Aucune coordonnée fournie ; cet enregistrement n’a pas d’épingle.' })}</dd></div>
      <div className="kv"><dt className="k">{tr({ en: 'Source passport', fr: 'Passeport de source' })}</dt><dd className="v"><Link href={`/sources/?datasetId=${encodeURIComponent(observation.datasetId)}`}>{observation.datasetId}</Link></dd></div>
    </dl>
    </details>
    <ul className="small">{observation.limitations.map((limitation, index) => <li key={index}>{limitation}</li>)}</ul>
  </div>;
}
