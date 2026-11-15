'use client';
/**
 * World Explorer detail panels (T15): one event (verbatim source title, publisher link, dates,
 * location precision, related events, code-only holding links with their basis) with its optional
 * audited event brief, and one country (exposure with basis, top events, macro facts).
 * A link between an event and a holding is a documented match; no impact is estimated here.
 */
import Link from 'next/link';
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import type {
  HoldingExposure, Profile, Run, WorldCountryResponse, WorldEvent, WorldEventResponse,
} from '../../contracts/types';
import { getApiClient } from '../../api/index';
import { asApiError, type ApiRequestError } from '../../api/errors';
import { profileKey, useApp } from '../../state/app';
import { useQuery } from '../../state/useQuery';
import { useRun } from '../../state/useRun';
import { Card } from '../../components/common/Page';
import { ErrorState, Loading, Unavailable } from '../../components/common/States';
import { ExternalLink } from '../../components/common/ExternalLink';
import { EvidenceChip, FactChip, FactScopeProvider, type FactScope } from '../../components/common/FactDrawer';
import { RunStatusBadge } from '../../components/common/Badges';
import { BriefView } from '../../components/run/BriefView';
import { RunTimeline } from '../../components/run/RunTimeline';
import {
  EVENT_CATEGORY, EVENT_ORIGIN, EXPOSURE_BASIS, EXPOSURE_IMPACT, LINK_TYPE, LOCATION_PRECISION, RUN_STATUS, SOURCE_TYPE,
  THEME_TAG, labelOf,
} from '../../lib/labels';
import { fmtDate, fmtDateTime, fmtNumber, fmtPct } from '../../lib/format';
import { countryLabel, isKnownIso3 } from '../../lib/geo';
import { isTerminal } from '../../lib/runs';
import { briefImpactStatement, briefOtherProfileId, decisionInvestigationUrl } from '../../lib/world';

const LANG_TAG = /^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$/;
/** `lang` attribute for verbatim source text, when the source states a usable language tag. */
export function sourceLang(event: Pick<WorldEvent, 'sources'>): string | undefined {
  const lang = event.sources[0]?.lang;
  return lang && LANG_TAG.test(lang) ? lang : undefined;
}

export function EventLine({ event }: { event: WorldEvent }) {
  const { tr, lang } = useApp();
  const country = event.location.countryIso3;
  return (
    <span className="small muted block">
      {fmtDate(event.occurredAt, lang)} · {labelOf(EVENT_CATEGORY, event.category, lang)}
      {' · '}{country ? countryLabel(country, lang) : tr({ en: 'no country stated', fr: 'pays non indiqué' })}
      {' · '}{event.sources[0]?.publisher ?? '—'}
    </span>
  );
}

function ExposureTable({ exposures, inRun, eventId, profileId, sourceRunId }: { exposures: readonly HoldingExposure[]; inRun: boolean; eventId: string; profileId: string; sourceRunId?: string }) {
  const { tr, lang } = useApp();
  return (
    <div className="table-scroll" role="region" aria-label={tr({ en: 'Holdings linked to this event', fr: 'Positions liées à cet événement' })} tabIndex={0}>
      <table className="data-table">
        <thead>
          <tr>
            <th scope="col">{tr({ en: 'Holding', fr: 'Position' })}</th>
            <th scope="col" className="num-col">{tr({ en: 'Weight', fr: 'Poids' })}</th>
            <th scope="col">{tr({ en: 'Basis of the link', fr: 'Fondement du lien' })}</th>
            <th scope="col">{tr({ en: 'Financial impact', fr: 'Impact financier' })}</th>
          </tr>
        </thead>
        <tbody>
          {exposures.map((exposure, i) => (
            <tr key={`${exposure.ticker}-${exposure.linkType}-${i}`}>
              <th scope="row" className="mono">{exposure.ticker}<br /><Link className="small" href={decisionInvestigationUrl(eventId, profileId, exposure.ticker, sourceRunId)}>{tr({ en: 'Investigate', fr: 'Examiner' })}</Link></th>
              <td className="num-col num">{fmtPct(exposure.weightPct, lang)}</td>
              <td>
                <span className="block">{labelOf(LINK_TYPE, exposure.linkType, lang)}</span>
                <span className="block small muted">{tr(exposure.note)}</span>
                {exposure.evidenceIds.length > 0 && (
                  <span className="block small">
                    {tr({ en: 'Evidence', fr: 'Preuves' })}:{' '}
                    {inRun
                      ? exposure.evidenceIds.map(id => <EvidenceChip key={id} evidenceId={id} display={id} />)
                      : <span className="mono">{exposure.evidenceIds.join(', ')}</span>}
                  </span>
                )}
              </td>
              <td>
                <span className={`pill ${exposure.impact === 'measured_price_move' ? 's-tension' : 's-nee'}`}>{labelOf(EXPOSURE_IMPACT, exposure.impact, lang)}</span>
                {exposure.impact === 'measured_price_move' && exposure.impactFactId && (
                  <span className="block small">
                    {inRun
                      ? <FactChip factId={exposure.impactFactId} />
                      : <>{tr({ en: 'Observation recorded as fact', fr: 'Observation enregistrée comme fait' })} <span className="mono">{exposure.impactFactId}</span></>}
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function EventPanel({ eventId, profile, runId, onSelectEvent, onSelectCountry, onRun, onClose }: {
  eventId: string; profile: Profile; runId: string | null;
  onSelectEvent: (eventId: string) => void; onSelectCountry: (iso3: string) => void;
  onRun: (runId: string | null) => void; onClose: () => void;
}) {
  const app = useApp();
  const { tr, lang } = app;
  const key = profileKey(app);
  const detail = useQuery<WorldEventResponse>(key ? `world-event|${key}|${eventId}` : null,
    signal => getApiClient().worldEvent(eventId, profile.profileId, signal));
  const ref = useRef<HTMLDivElement | null>(null);
  useEffect(() => { ref.current?.focus(); }, [eventId]);

  const [creatingFor, setCreatingFor] = useState<string | null>(null);
  const creating = creatingFor === eventId;
  const [createError, setCreateError] = useState<ApiRequestError | null>(null);
  useEffect(() => { setCreateError(null); }, [eventId]);
  // The event this panel shows now; null once the panel is closed. A "Brief me" that answers after
  // the reader moved to another event or closed the panel must not navigate back to its event,
  // re-open the panel, or report its failure under another event.
  const liveEvent = useRef<string | null>(null);
  useLayoutEffect(() => {
    liveEvent.current = eventId;
    return () => { liveEvent.current = null; };
  }, [eventId]);
  const briefMe = async () => {
    const startedFor = eventId;
    setCreatingFor(startedFor); setCreateError(null);
    try {
      const created = await getApiClient().createRun(
        { kind: 'event_brief', profileId: profile.profileId, lang, eventId: startedFor }, `event-brief-${crypto.randomUUID()}`);
      if (liveEvent.current === startedFor) onRun(created.runId);
    } catch (error) {
      if (liveEvent.current === startedFor) setCreateError(asApiError(error));
    } finally { setCreatingFor(current => (current === startedFor ? null : current)); }
  };

  const event = detail.data?.event ?? null;
  const location = event?.location ?? null;

  return (
    <div ref={ref} tabIndex={-1} className="focus-target" id="event-panel">
      <Card title={tr({ en: 'Event', fr: 'Événement' })}
        actions={<button type="button" className="btn ghost btn-sm" onClick={onClose}>{tr({ en: 'Close event', fr: 'Fermer l’événement' })}</button>}>
        {detail.loading && <Loading />}
        {detail.error && <ErrorState error={detail.error} onRetry={detail.reload}
          {...(detail.error.code === 'not_found' ? { title: tr({ en: 'This event is not in the loaded dataset.', fr: 'Cet événement n’est pas dans le jeu de données chargé.' }) } : {})} />}
        {event && location && detail.data && (
          <>
            <p className="eyebrow">{labelOf(EVENT_CATEGORY, event.category, lang)} · {labelOf(EVENT_ORIGIN, event.origin, lang)}</p>
            <h3 className="serif event-title" lang={sourceLang(event)}>{event.title}</h3>

            <dl>
              <div className="kv"><dt className="k">{tr({ en: 'Occurred', fr: 'Survenu le' })}</dt><dd className="v">{fmtDate(event.occurredAt, lang)}</dd></div>
              <div className="kv"><dt className="k">{tr({ en: 'Published', fr: 'Publié' })}</dt>
                <dd className="v">{event.publishedAt ? fmtDateTime(event.publishedAt, lang) : tr({ en: 'Not stated by the source', fr: 'Non indiqué par la source' })}</dd></div>
              <div className="kv"><dt className="k">{tr({ en: 'Location', fr: 'Lieu' })}</dt>
                <dd className="v">
                  <span className="block">
                    {location.placeName ?? tr({ en: 'No place name stated', fr: 'Aucun nom de lieu indiqué' })}
                    {location.countryIso3 && isKnownIso3(location.countryIso3) && (
                      <> · <button type="button" className="linklike" onClick={() => onSelectCountry(location.countryIso3 ?? '')}>{countryLabel(location.countryIso3, lang)}</button></>
                    )}
                    {location.countryIso3 && !isKnownIso3(location.countryIso3) && <> · <span className="mono">{location.countryIso3}</span></>}
                    {!location.countryIso3 && <> · {tr({ en: 'no country stated (for example an ocean region)', fr: 'pays non indiqué (par exemple une région océanique)' })}</>}
                  </span>
                  <span className="block"><span className="tag">{labelOf(LOCATION_PRECISION, location.precision, lang)}</span></span>
                  <span className="block small muted mono">{fmtNumber(location.lat, lang, 2)}, {fmtNumber(location.lon, lang, 2)}</span>
                </dd></div>
              <div className="kv"><dt className="k">{tr({ en: 'Sources', fr: 'Sources' })}</dt>
                <dd className="v">
                  <ul className="list-plain">
                    {event.sources.map((source, i) => (
                      <li key={`${source.url}-${i}`}>
                        <strong>{source.publisher}</strong> · {labelOf(SOURCE_TYPE, source.sourceType, lang)}
                        <span className="block" lang={LANG_TAG.test(source.lang) ? source.lang : undefined}><ExternalLink href={source.url}>{source.title}</ExternalLink></span>
                        <span className="block small muted">{source.publishedAt ? fmtDateTime(source.publishedAt, lang) : tr({ en: 'publication time not stated by the source', fr: 'heure de publication non indiquée par la source' })}</span>
                      </li>
                    ))}
                  </ul>
                </dd></div>
              <div className="kv"><dt className="k">{tr({ en: 'Documented matches', fr: 'Correspondances documentées' })}</dt>
                <dd className="v">
                  {event.relatedTickers.length + event.relatedThemes.length + event.relatedCountries.length === 0
                    ? tr({ en: 'None recorded.', fr: 'Aucune enregistrée.' })
                    : (
                      <>
                        {event.relatedTickers.map(ticker => <span key={ticker} className="tag mono">{ticker}</span>)}
                        {event.relatedThemes.map(theme => <span key={theme} className="tag">{labelOf(THEME_TAG, theme, lang)}</span>)}
                        {event.relatedCountries.map(code => <span key={code} className="tag">{countryLabel(code, lang)}</span>)}
                      </>
                    )}
                </dd></div>
              <div className="kv"><dt className="k">{tr({ en: 'Feed ranking score', fr: 'Score de classement du fil' })}</dt>
                <dd className="v"><span className="num">{fmtNumber(event.importance, lang, 2)}</span> <span className="small muted">{tr({ en: '(0 to 1; orders the feed, not a measure of impact)', fr: '(de 0 à 1 ; ordonne le fil, ce n’est pas une mesure d’impact)' })}</span></dd></div>
              <div className="kv"><dt className="k">{tr({ en: 'Dataset', fr: 'Jeu de données' })}</dt>
                <dd className="v"><Link className="mono" href={`/sources/?datasetId=${encodeURIComponent(event.datasetId)}&dataVersion=${encodeURIComponent(event.dataVersion)}`}>{event.datasetId}</Link> · <span className="mono small break">{event.dataVersion}</span></dd></div>
            </dl>

            <h3 className="h4">{tr({ en: `Holdings of ${profile.name} linked to this event`, fr: `Positions de ${profile.name} liées à cet événement` })}</h3>
            {detail.data.exposures.length === 0 ? (
              <p className="small muted">{tr({ en: 'No documented link between this event and a holding was found by the code matches. This is not evidence that the portfolio is unaffected.', fr: 'Aucun lien documenté entre cet événement et une position n’a été trouvé par les correspondances du code. Cela ne prouve pas que le portefeuille n’est pas touché.' })}</p>
            ) : (
              <>
                <p className="small"><strong>{detail.data.exposures.every(exposure => exposure.impact === 'not_established')
                  ? tr({ en: 'Potential exposure identified, financial impact not established.', fr: 'Exposition potentielle repérée, impact financier non établi.' })
                  : tr({ en: 'Potential exposure identified. Where a price change was observed, it is an observation, not proof that the event caused it.', fr: 'Exposition potentielle repérée. Lorsqu’une variation de prix a été observée, c’est une observation, pas la preuve que l’événement l’a causée.' })}</strong>{' '}
                  {tr({ en: 'Each row states why the holding is listed. A link is a documented match, not an estimate of gain or loss.', fr: 'Chaque ligne indique pourquoi la position est listée. Un lien est une correspondance documentée, pas une estimation de gain ou de perte.' })}</p>
                <ExposureTable exposures={detail.data.exposures} inRun={false} eventId={eventId} profileId={profile.profileId} />
              </>
            )}

            <h3 className="h4">{tr({ en: 'Related events (same country, within 7 days)', fr: 'Événements connexes (même pays, à 7 jours près)' })}</h3>
            {detail.data.related.length === 0
              ? <p className="small muted">{tr({ en: 'None in the loaded dataset.', fr: 'Aucun dans le jeu de données chargé.' })}</p>
              : (
                <ul className="list-plain">
                  {detail.data.related.map(related => (
                    <li key={related.eventId}>
                      <button type="button" className="linklike" lang={sourceLang(related)} onClick={() => onSelectEvent(related.eventId)}>{related.title}</button>
                      <EventLine event={related} />
                    </li>
                  ))}
                </ul>
              )}

            <h3 className="h4">{tr({ en: 'Audited event brief', fr: 'Note d’événement auditée' })}</h3>
            <div className="row-actions">
              <button type="button" className="btn gold" onClick={() => void briefMe()} disabled={creating}>
                {tr({ en: 'Brief me', fr: 'Rédiger une note' })}
              </button>
              <span className="small muted">{tr({ en: 'Writes an audited explanation for this event.', fr: 'Rédige une explication auditée pour cet événement.' })}</span>
            </div>
            {creating && <Loading label={tr({ en: 'Creating the run…', fr: 'Création de l’exécution…' })} />}
            {createError && (
              <ErrorState error={createError} onRetry={() => void briefMe()}
                title={tr({ en: 'The event brief could not be started. No brief was written; the event details above are unaffected.', fr: 'La note d’événement n’a pas pu être lancée. Aucune note n’a été rédigée ; les détails de l’événement ci-dessus ne sont pas touchés.' })} />
            )}
          </>
        )}
        {runId && <EventBriefRun runId={runId} eventId={eventId} profile={profile} onSelectEvent={onSelectEvent} onDismiss={() => onRun(null)} />}
      </Card>
    </div>
  );
}

function EventBriefRun({ runId, eventId, profile, onSelectEvent, onDismiss }: {
  runId: string; eventId: string; profile: Profile; onSelectEvent: (eventId: string) => void; onDismiss: () => void;
}) {
  const { tr, lang, announce } = useApp();
  const polled = useRun(runId, finished => announce(`${tr({ en: 'Event brief', fr: 'Note d’événement' })}: ${labelOf(RUN_STATUS, finished.status, lang)}`));
  const run = polled.run;
  return (
    <section className="event-brief" aria-labelledby="event-brief-title">
      <div className="card-head">
        <h3 className="h4" id="event-brief-title">{tr({ en: 'Event brief', fr: 'Note d’événement' })}</h3>
        <button type="button" className="btn ghost btn-sm" onClick={onDismiss}>{tr({ en: 'Hide', fr: 'Masquer' })}</button>
      </div>
      {polled.loading && !run && <Loading />}
      {polled.error && <ErrorState error={polled.error} onRetry={polled.reload}
        {...(polled.error.code === 'not_found' ? { title: tr({ en: 'This run does not exist or belongs to another session.', fr: 'Cette exécution n’existe pas ou appartient à une autre session.' }) } : {})} />}
      {polled.pollError && (
        <p className="small muted" role="status">{tr({ en: 'Connection lost, retrying…', fr: 'Connexion perdue, nouvel essai…' })}</p>
      )}
      {run && <EventBriefBody run={run} eventId={eventId} profile={profile} onSelectEvent={onSelectEvent} />}
    </section>
  );
}

function EventBriefBody({ run, eventId, profile, onSelectEvent }: {
  run: Run; eventId: string; profile: Profile; onSelectEvent: (eventId: string) => void;
}) {
  const { tr, lang, profiles, selectProfile } = useApp();
  const scope = useMemo<FactScope>(() => ({ kind: 'run', runId: run.runId, facts: run.facts, evidence: run.evidence }), [run]);
  const runEventId = run.input.kind === 'event_brief' ? run.input.eventId : null;
  const result = run.result?.kind === 'event_brief' ? run.result.eventBrief : null;
  // The run stays in the URL across a persona switch: a brief written for another profile is labelled, never shown as this one's.
  const otherProfileId = briefOtherProfileId(run.profileId, profile.profileId);
  const otherProfile = otherProfileId ? profiles.find(item => item.profileId === otherProfileId) ?? null : null;
  const ownerName = otherProfileId ? (otherProfile?.name ?? otherProfileId) : profile.name;

  if (run.kind !== 'event_brief') {
    return (
      <Unavailable title={tr({ en: 'This run is not an event brief.', fr: 'Cette exécution n’est pas une note d’événement.' })}>
        <Link href={`/evidence-audit/?runId=${encodeURIComponent(run.runId)}`}>{tr({ en: 'Open it in Evidence & Audit', fr: 'L’ouvrir dans Preuves et audit' })}</Link>
      </Unavailable>
    );
  }
  return (
    <FactScopeProvider scope={scope}>
      {otherProfileId && (
        <p className="stale-note" role="note">
          {tr({
            en: `This brief was written for another fictional profile, ${ownerName}, not for ${profile.name}. The holdings and figures below are those of ${ownerName}.`,
            fr: `Cette note a été rédigée pour un autre profil fictif, ${ownerName}, et non pour ${profile.name}. Les positions et les chiffres ci-dessous sont ceux de ${ownerName}.`,
          })}{' '}
          {otherProfile && (
            <button type="button" className="linklike" onClick={() => selectProfile(otherProfile.profileId)}>
              {tr({ en: 'Switch to', fr: 'Basculer vers' })} {otherProfile.name}
            </button>
          )}
        </p>
      )}
      {runEventId && runEventId !== eventId && (
        <p className="stale-note" role="note">
          {tr({ en: 'This brief was written for another event, not the one shown above.', fr: 'Cette note a été rédigée pour un autre événement que celui affiché ci-dessus.' })}{' '}
          <button type="button" className="linklike" onClick={() => onSelectEvent(runEventId)}>{tr({ en: 'Open that event', fr: 'Ouvrir cet événement' })}</button>
        </p>
      )}
      {!isTerminal(run.status) && (
        <p className="small"><RunStatusBadge status={run.status} /> {tr({ en: 'Steps appear only as they actually execute.', fr: 'Les étapes apparaissent seulement quand elles s’exécutent réellement.' })}</p>
      )}
      {run.status === 'failed' && (
        <p className="small">{tr({ en: 'No brief was written. The event details above come from the dataset and are unaffected.', fr: 'Aucune note n’a été rédigée. Les détails de l’événement ci-dessus viennent du jeu de données et ne sont pas touchés.' })}
          {run.error?.requestId && <span className="mono muted"> · {tr({ en: 'Request', fr: 'Requête' })} {run.error.requestId}</span>}</p>
      )}
      {result && (
        <>
          {/* Decided from the exposures the code returned: no linked holding, no "exposure identified". */}
          <p className="impact-statement" role="note">{tr(briefImpactStatement(result))}</p>
          <p className="small muted">
            {tr({ en: 'Written for', fr: 'Rédigée pour' })}: <span lang={sourceLang(result.event)}>{result.event.title}</span>
            {' · '}{tr({ en: 'Profile', fr: 'Profil' })}: {ownerName}
          </p>
          {result.exposures.length > 0 && (
            <>
              <h4 className="h4">{tr({ en: `Holdings of ${ownerName} exposed, with the basis of each link`, fr: `Positions de ${ownerName} exposées, avec le fondement de chaque lien` })}</h4>
              <ExposureTable exposures={result.exposures} inRun eventId={runEventId ?? eventId} profileId={run.profileId ?? profile.profileId} sourceRunId={run.runId} />
            </>
          )}
          <BriefView brief={result.brief} />
          <p className="row-actions small">
            <Link href={`/evidence-audit/?runId=${encodeURIComponent(run.runId)}`}>{tr({ en: 'Open Evidence & Audit for this run', fr: 'Ouvrir Preuves et audit pour cette exécution' })}</Link>
          </p>
        </>
      )}
      <details open={!result}>
        <summary className="h4">{tr({ en: 'Execution trace', fr: 'Trace d’exécution' })} · {labelOf(RUN_STATUS, run.status, lang)}</summary>
        <RunTimeline run={run} />
      </details>
    </FactScopeProvider>
  );
}

export function CountryPanel({ iso3, profile, from, to, onSelectEvent, onClose }: {
  iso3: string; profile: Profile; from: string; to: string; onSelectEvent: (eventId: string) => void; onClose: () => void;
}) {
  const app = useApp();
  const { tr, lang } = app;
  const key = profileKey(app);
  const range = from && to ? { from, to } : {};
  const detail = useQuery<WorldCountryResponse>(key ? `world-country|${key}|${iso3}|${from}|${to}` : null,
    signal => getApiClient().worldCountry(iso3, { profileId: profile.profileId, ...range }, signal));
  const ref = useRef<HTMLDivElement | null>(null);
  useEffect(() => { ref.current?.focus(); }, [iso3]);
  const data = detail.data;
  const macroScope = useMemo<FactScope | null>(() => (data ? {
    kind: 'local',
    label: { en: `Macro facts returned with the country panel for ${iso3}. Not part of any run ledger.`, fr: `Faits macro renvoyés avec le panneau du pays ${iso3}. Hors de tout registre d’exécution.` },
    facts: Object.fromEntries(data.macro.map(fact => [fact.id, fact])),
  } : null), [data, iso3]);

  return (
    <div ref={ref} tabIndex={-1} className="focus-target" id="country-panel">
      {/* For a code outside the backend's reference table the API returns the code as the name: use the CLDR name then. */}
      <Card title={`${tr({ en: 'Country', fr: 'Pays' })} · ${data && tr(data.name) !== data.countryIso3 ? tr(data.name) : countryLabel(iso3, lang)}`}
        actions={<button type="button" className="btn ghost btn-sm" onClick={onClose}>{tr({ en: 'Close country', fr: 'Fermer le pays' })}</button>}>
        {detail.loading && <Loading />}
        {detail.error && <ErrorState error={detail.error} onRetry={detail.reload}
          {...(detail.error.code === 'not_found' ? { title: tr({ en: 'No data is loaded for this country code.', fr: 'Aucune donnée n’est chargée pour ce code de pays.' }) } : {})} />}
        {data && macroScope && (
          <>
            <p className="small mono muted">{data.countryIso3}</p>
            <h3 className="h4">{tr({ en: `Exposure of ${profile.name}`, fr: `Exposition de ${profile.name}` })}</h3>
            {data.exposure ? (
              <>
                <p><strong className="num">{fmtPct(data.exposure.weightPct, lang)}</strong> {tr({ en: 'of the portfolio', fr: 'du portefeuille' })} · <span className="tag">{tr({ en: 'Basis', fr: 'Fondement' })}: {labelOf(EXPOSURE_BASIS, data.exposure.basis, lang)}</span></p>
                {data.exposure.holdings.length > 0 && (
                  <ul className="small holdings-inline">
                    {data.exposure.holdings.map(holding => <li key={holding.ticker}><span className="mono">{holding.ticker}</span> <span className="num">{fmtPct(holding.weightPct, lang)}</span></li>)}
                  </ul>
                )}
                <p className="small muted">{tr({ en: 'A weight by listing country or fund look-through is a proxy for where a holding is listed or invested, not a measured sensitivity to events there.', fr: 'Un poids par pays de cotation ou par transparence des fonds est une approximation du lieu de cotation ou d’investissement, pas une sensibilité mesurée aux événements locaux.' })}</p>
              </>
            ) : (
              <p className="small muted">{tr({ en: 'No exposure to this country was returned for this portfolio.', fr: 'Aucune exposition à ce pays n’a été renvoyée pour ce portefeuille.' })}</p>
            )}

            <h3 className="h4">{tr({ en: 'Top events by ranking score', fr: 'Principaux événements par score de classement' })}{from && to ? ` (${fmtDate(from, lang)} → ${fmtDate(to, lang)})` : ''}</h3>
            {data.events.length === 0
              ? <p className="small muted">{tr({ en: 'No event for this country in the loaded dataset for this interval.', fr: 'Aucun événement pour ce pays dans le jeu de données chargé sur cet intervalle.' })}</p>
              : (
                <ul className="list-plain">
                  {data.events.map(event => (
                    <li key={event.eventId}>
                      <button type="button" className="linklike" lang={sourceLang(event)} onClick={() => onSelectEvent(event.eventId)}>{event.title}</button>
                      <EventLine event={event} />
                    </li>
                  ))}
                </ul>
              )}

            <h3 className="h4">{tr({ en: 'Macro facts', fr: 'Faits macroéconomiques' })}</h3>
            {data.macro.length === 0
              ? <p className="small muted">{tr({ en: 'No macro fact was returned for this country. Policy rate and inflation series are loaded only for Canada and the United States.', fr: 'Aucun fait macro n’a été renvoyé pour ce pays. Les séries de taux directeur et d’inflation ne sont chargées que pour le Canada et les États-Unis.' })}</p>
              : (
                <FactScopeProvider scope={macroScope}>
                  <ul className="list-plain">
                    {data.macro.map(fact => (
                      <li key={fact.id}>{tr(fact.label)}: <FactChip factId={fact.id} /> <span className="small muted">{tr({ en: 'as of', fr: 'au' })} {fmtDate(fact.asOf, lang)}</span></li>
                    ))}
                  </ul>
                </FactScopeProvider>
              )}
          </>
        )}
      </Card>
    </div>
  );
}
