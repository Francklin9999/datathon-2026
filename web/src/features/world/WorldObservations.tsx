'use client';
import Link from 'next/link';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { WorldObservation, WorldObservationsResponse } from '../../contracts/types';
import { getApiClient } from '../../api/index';
import { asApiError, isAbort, type ApiRequestError } from '../../api/errors';
import { profileKey, useApp } from '../../state/app';
import { Card } from '../../components/common/Page';
import { Empty, ErrorState, Loading } from '../../components/common/States';
import { ExternalLink } from '../../components/common/ExternalLink';
import { countryLabel } from '../../lib/geo';
import { fmtDateTime } from '../../lib/format';
import { WORLD_MODES, type WorldMode } from '../../lib/world';
import type { GlobePin } from './globeStyle';

type ObservationState = {
  key: string | null; page: WorldObservationsResponse | null; loading: boolean; loadingMore: boolean;
  error: ApiRequestError | null; moreError: ApiRequestError | null; loadedAt: string | null;
};
const INITIAL: ObservationState = { key: null, page: null, loading: false, loadingMore: false, error: null, moreError: null, loadedAt: null };

/** Provider observations remain separate from portfolio matches; no relationship is inferred here. */
export function WorldObservations({ mode, bbox, country, q, from, to, selectedId, onPins, onSelect }: {
  mode: WorldMode; bbox: string; country: string; q: string; from: string; to: string; selectedId: string | null;
  onPins: (pins: GlobePin[]) => void; onSelect: (id: string) => void;
}) {
  const app = useApp();
  const { tr, lang } = app;
  const scope = profileKey(app);
  const [useDates, setUseDates] = useState(false);
  const [markersOn, setMarkersOn] = useState(true);
  const [state, setState] = useState<ObservationState>(INITIAL);
  const [nonce, setNonce] = useState(0);
  const sourceMode = mode === 'portfolio' ? undefined : mode;
  const query = useMemo(() => ({
    ...(sourceMode ? { mode: sourceMode } : {}), ...(bbox ? { bbox } : {}),
    ...(country ? { country: [country] } : {}), ...(q ? { q } : {}),
    ...(useDates && from && to ? { from, to } : {}), limit: 100,
  }), [sourceMode, bbox, country, q, useDates, from, to]);
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
  const pins = useMemo<GlobePin[]>(() => (markersOn ? page?.items ?? [] : []).flatMap(row => row.location ? [{
    id: `observation:${row.id}`, kind: 'observation' as const, lat: row.location.lat, lng: row.location.lon,
    label: row.title, countryLevel: row.location.precision === 'country', weight: .2, geometry: row.location.geometry ?? null,
  }] : []).slice(0, 300), [page, markersOn]);
  useEffect(() => { onPins(pins); return () => onPins([]); }, [pins, onPins]);
  const loadMore = useCallback(async () => {
    if (!page?.nextCursor || state.loadingMore || state.loading) return;
    const startedFor = key;
    setState(previous => ({ ...previous, loadingMore: true, moreError: null }));
    try {
      const next = await getApiClient().worldObservations({ ...query, cursor: page.nextCursor });
      if (liveKey.current !== startedFor) return;
      setState(previous => {
        const seen = new Set(previous.page?.items.map(row => row.id));
        return { ...previous, loadingMore: false, page: { ...next, items: [...(previous.page?.items ?? []), ...next.items.filter(row => !seen.has(row.id))] } };
      });
    } catch (error) {
      if (liveKey.current === startedFor) setState(previous => ({ ...previous, loadingMore: false, moreError: asApiError(error) }));
    }
  }, [page, key, query, state.loadingMore, state.loading]);
  const selected = page?.items.find(row => `observation:${row.id}` === selectedId);
  const title = WORLD_MODES.find(item => item.id === mode)!.title;
  const availability = sourceMode ? page?.modes.find(item => item.mode === sourceMode) : null;
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
      <p className="small" role="status">{tr({ en: `${page.items.length} loaded of ${page.total} matching observations; ${pins.length} pins offered to the globe. Captured ${page.capturedAt ?? 'not supplied'}; version ${page.dataVersion ?? 'not supplied'}.`, fr: `${page.items.length} observations chargées sur ${page.total} correspondantes ; ${pins.length} épingles proposées au globe. Capture ${page.capturedAt ?? 'non fournie'} ; version ${page.dataVersion ?? 'non fournie'}.` })}</p>
      {!page.items.length && !state.loading && <Empty>{tr({ en: 'No loaded observation matches this mode and geographic query. Broaden the area or date filters; source coverage may be unavailable.', fr: 'Aucune observation chargée ne correspond au mode et à la zone. Élargissez la zone ou les dates ; les sources peuvent être indisponibles.' })}</Empty>}
      {selected && <ObservationDetail observation={selected} />}
      <ol className="feed-list" aria-label={tr({ en: 'Source observations', fr: 'Observations sourcées' })}>
        {page.items.map(row => <li key={row.id}><button type="button" className="feed-item" aria-current={`observation:${row.id}` === selectedId ? 'true' : undefined} onClick={() => onSelect(`observation:${row.id}`)}>
          <span className="feed-title">{row.title}</span><span className="small muted block">{row.source.name} · {fmtDateTime(row.occurredAt, lang)} · {row.location?.countryIso3 ? countryLabel(row.location.countryIso3, lang) : tr({ en: 'country not stated', fr: 'pays non indiqué' })}</span>
          <span className="small muted block">{row.location?.precision ?? tr({ en: 'No source coordinates', fr: 'Aucune coordonnée de source' })} · {row.timeBasis}</span>
        </button></li>)}
      </ol>
      {page.nextCursor && <button className="btn ghost" type="button" onClick={() => void loadMore()} disabled={state.loadingMore || state.loading}>{tr({ en: 'Load more observations', fr: 'Charger plus d’observations' })}</button>}
      {state.loadingMore && <Loading />}
      {state.moreError && <ErrorState error={state.moreError} onRetry={() => void loadMore()} />}
    </>}
  </Card>;
}

function ObservationDetail({ observation }: { observation: WorldObservation }) {
  const { tr, lang } = useApp();
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { ref.current?.focus({ preventScroll: true }); }, [observation.id]);
  return <div className="world-observation-detail focus-target" ref={ref} tabIndex={-1}>
    <h3>{observation.title}</h3>
    <p className="small">{observation.summary}</p>
    <p className="small muted">{tr({ en: 'Source record description; no generated AI summary or financial impact model is implied.', fr: 'Description de l’enregistrement source ; aucune synthèse IA ni modélisation financière implicite.' })}</p>
    <dl>
      <div className="kv"><dt className="k">{tr({ en: 'Original source', fr: 'Source originale' })}</dt><dd className="v"><ExternalLink href={observation.source.url}>{observation.source.name}</ExternalLink></dd></div>
      <div className="kv"><dt className="k">{tr({ en: 'Observed / time basis', fr: 'Observation / fondement temporel' })}</dt><dd className="v">{fmtDateTime(observation.occurredAt, lang)} · {observation.timeBasis}</dd></div>
      <div className="kv"><dt className="k">{tr({ en: 'Publication', fr: 'Publication' })}</dt><dd className="v">{observation.publishedAt ? fmtDateTime(observation.publishedAt, lang) : tr({ en: 'Not stated', fr: 'Non indiquée' })}</dd></div>
      <div className="kv"><dt className="k">{tr({ en: 'Retrieved', fr: 'Collecté' })}</dt><dd className="v">{fmtDateTime(observation.retrievedAt, lang)}</dd></div>
      <div className="kv"><dt className="k">{tr({ en: 'Source geometry', fr: 'Géométrie de source' })}</dt><dd className="v">{observation.location ? `${observation.location.precision} · ${observation.location.lat}, ${observation.location.lon}` : tr({ en: 'No coordinates supplied; this record has no map pin.', fr: 'Aucune coordonnée fournie ; cet enregistrement n’a pas d’épingle.' })}</dd></div>
      <div className="kv"><dt className="k">{tr({ en: 'Source passport', fr: 'Passeport de source' })}</dt><dd className="v"><Link href={`/sources/?datasetId=${encodeURIComponent(observation.datasetId)}`}>{observation.datasetId}</Link></dd></div>
    </dl>
    <ul className="small">{observation.limitations.map((limitation, index) => <li key={index}>{limitation}</li>)}</ul>
    <p className="small"><strong>{tr({ en: 'No holding relationship or financial impact is established by this observation.', fr: 'Aucun lien avec une position ni impact financier n’est établi par cette observation.' })}</strong></p>
  </div>;
}
