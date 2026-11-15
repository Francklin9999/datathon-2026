'use client';
/**
 * Sources — dataset passports and limitations (T13, web/page-specs/sources.md). Planned sources never
 * get fabricated dates/checks; unknown licences stay "unknown"; a passport opened from a fact warns
 * when its data version differs from the fact's snapshot (SRC-04).
 */
import Link from 'next/link';
import { SourceDirectory } from './SourceDirectory';
import { useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useRef } from 'react';
import type { DatasetPassport, DatasetsResponse } from '../../contracts/types';
import { getApiClient } from '../../api/index';
import { useApp } from '../../state/app';
import { useQuery } from '../../state/useQuery';
import { Card, PageHeader } from '../../components/common/Page';
import { Empty, ErrorState, Loading } from '../../components/common/States';
import { ExternalLink } from '../../components/common/ExternalLink';
import { LimitationList } from '../../components/common/FactDrawer';
import { DATASET_STATUS, LIMITATION, TRAP_STATUS, labelOf } from '../../lib/labels';
import { fmtDate, fmtDateTime, fmtNumber } from '../../lib/format';

function licenceText(passport: DatasetPassport, unknown: string): string {
  const value = passport.licence.trim();
  return !value || value.toLowerCase() === 'unknown' ? unknown : value;
}

export function SourcesPage() {
  const { tr, lang, sessionId, meta } = useApp();
  const params = useSearchParams();
  const router = useRouter();
  const datasetId = params.get('datasetId');
  const pinnedVersion = params.get('dataVersion');
  const list = useQuery<DatasetsResponse>(sessionId && meta ? `datasets|${sessionId}|${meta.dataVersion}` : null,
    signal => getApiClient().datasets(signal));
  const detail = useQuery<DatasetPassport>(datasetId && sessionId && meta ? `dataset|${sessionId}|${meta.dataVersion}|${datasetId}` : null,
    signal => getApiClient().dataset(datasetId ?? '', signal));
  const detailRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => { if (detail.data) detailRef.current?.focus(); }, [detail.data]);

  const unknown = tr({ en: 'Licence unknown', fr: 'Licence inconnue' });

  return (
    <>
      <PageHeader eyebrow={tr({ en: 'Data room', fr: 'Salle des données' })} title={tr({ en: 'Sources and dataset passports', fr: 'Sources et passeports des jeux de données' })}>
        <p className="page-sub">{tr({ en: 'What each dataset is, where it comes from, how it is processed and what it cannot tell you.', fr: 'Ce qu’est chaque jeu de données, sa provenance, son traitement et ce qu’il ne peut pas dire.' })}</p>
      </PageHeader>

      {datasetId && (
        <div ref={detailRef} tabIndex={-1}>
          <Card id="passport" title={`${tr({ en: 'Passport', fr: 'Passeport' })} · ${datasetId}`}
            actions={<button type="button" className="btn ghost btn-sm" onClick={() => router.push('/sources/')}>{tr({ en: 'Close passport', fr: 'Fermer le passeport' })}</button>}>
            {detail.loading && <Loading />}
            {detail.error && <ErrorState error={detail.error} onRetry={detail.reload}
              {...(detail.error.code === 'not_found' ? { title: tr({ en: 'No passport exists for this dataset ID.', fr: 'Aucun passeport n’existe pour cet identifiant.' }) } : {})} />}
            {detail.data && (
              <>
                {pinnedVersion && detail.data.dataVersion !== pinnedVersion && (
                  <p className="stale-note" role="alert">
                    {tr({
                      en: `The fact you came from was computed on ${pinnedVersion}; this passport describes ${detail.data.dataVersion ?? 'no loaded version'}. The API does not serve pinned historical passports.`,
                      fr: `Le fait d’origine a été calculé sur ${pinnedVersion} ; ce passeport décrit ${detail.data.dataVersion ?? 'aucune version chargée'}. L’API ne sert pas de passeports historiques épinglés.`,
                    })}
                  </p>
                )}
                <PassportDetail passport={detail.data} unknown={unknown} />
              </>
            )}
          </Card>
        </div>
      )}

      <SourceDirectory />
      {list.loading && <Loading />}
      {list.error && <ErrorState error={list.error} onRetry={list.reload}
        title={tr({ en: 'Dataset passports are unavailable. No source health is implied.', fr: 'Les passeports sont indisponibles. Aucun état des sources n’est supposé.' })} />}
      {list.data && (
        <>
          <Card id="datasets" title={tr({ en: 'Datasets', fr: 'Jeux de données' })}>
            {list.data.items.length === 0 ? <Empty>{tr({ en: 'No dataset passport was returned.', fr: 'Aucun passeport n’a été retourné.' })}</Empty> : (
              <div className="table-scroll" role="region" aria-label={tr({ en: 'Dataset passports', fr: 'Passeports des jeux de données' })} tabIndex={0}>
                <table className="data-table" style={{ minWidth: 960 }}>
                  <thead>
                    <tr>
                      <th scope="col">{tr({ en: 'Dataset', fr: 'Jeu de données' })}</th>
                      <th scope="col">{tr({ en: 'Status', fr: 'Statut' })}</th>
                      <th scope="col">{tr({ en: 'Provider', fr: 'Fournisseur' })}</th>
                      <th scope="col">{tr({ en: 'Retrieved', fr: 'Récupéré' })}</th>
                      <th scope="col">{tr({ en: 'Coverage', fr: 'Couverture' })}</th>
                      <th scope="col">{tr({ en: 'Frequency', fr: 'Fréquence' })}</th>
                      <th scope="col" className="num-col">{tr({ en: 'Rows', fr: 'Lignes' })}</th>
                      <th scope="col">{tr({ en: 'Version', fr: 'Version' })}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {list.data.items.map(p => (
                      <tr key={p.datasetId}>
                        <th scope="row">
                          <Link href={`/sources/?datasetId=${encodeURIComponent(p.datasetId)}`}>{tr(p.name)}</Link>
                          <span className="block small muted break">{tr(p.role)}</span>
                        </th>
                        <td>
                          <span className={`pill s-${p.status === 'in_use' ? 'pass' : p.status === 'planned' ? 'nee' : 'conflict'}`}>{labelOf(DATASET_STATUS, p.status, lang)}</span>
                          {p.rejectedReason && <span className="block small">{tr(p.rejectedReason)}</span>}
                        </td>
                        <td className="break">{p.source}<span className="block small muted">{licenceText(p, unknown)}</span></td>
                        <td>{p.retrievedOn ? fmtDate(p.retrievedOn, lang) : <span className="muted">{tr({ en: 'Not retrieved', fr: 'Non récupéré' })}</span>}</td>
                        <td>{p.coverage ? `${p.coverage.start} → ${p.coverage.end}` : '—'}</td>
                        <td>{p.frequency}</td>
                        <td className="num-col num">{p.rowCount === null ? '—' : fmtNumber(p.rowCount, lang, 0)}</td>
                        <td className="mono small">{p.dataVersion ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <Card id="traps" title={tr({ en: 'Known dataset traps and how they are treated', fr: 'Pièges connus des données et leur traitement' })}>
            {list.data.traps.length === 0 ? <Empty>{tr({ en: 'No trap mapping was returned.', fr: 'Aucune correspondance de pièges n’a été retournée.' })}</Empty> : (
              <ul className="list-plain">
                {list.data.traps.map(trap => (
                  <li key={trap.code}>
                    <span className={`pill s-${trap.status === 'handled' ? 'pass' : trap.status === 'disclosed' ? 'tension' : 'conflict'}`}>{labelOf(TRAP_STATUS, trap.status, lang)}</span>{' '}
                    <span className="mono small">{trap.code}</span>
                    <span className="block">{labelOf(LIMITATION, trap.code, lang)}</span>
                    <span className="block small muted">{tr({ en: 'Treatment', fr: 'Traitement' })}: {trap.handledBy}</span>
                  </li>
                ))}
              </ul>
            )}
            <p className="small muted">{tr({ en: '“Handled” is the API’s claim of an implemented, tested treatment; “disclosed” means the limitation is shown but not corrected.', fr: '« Traité » est l’affirmation de l’API d’un traitement implémenté et testé ; « divulgué » signifie que la limite est affichée sans être corrigée.' })}</p>
          </Card>
        </>
      )}
    </>
  );
}

function PassportDetail({ passport, unknown }: { passport: DatasetPassport; unknown: string }) {
  const { tr, lang } = useApp();
  const licence = licenceText(passport, unknown);
  return (
    <div>
      <p className="fact-label">{tr(passport.name)}</p>
      <p className="small muted">{tr(passport.role)}</p>
      <dl>
        <div className="kv"><dt className="k">{tr({ en: 'Status', fr: 'Statut' })}</dt><dd className="v">{labelOf(DATASET_STATUS, passport.status, lang)}{passport.rejectedReason ? ` — ${tr(passport.rejectedReason)}` : ''}</dd></div>
        <div className="kv"><dt className="k">{tr({ en: 'Source', fr: 'Source' })}</dt><dd className="v">{passport.sourceUrl ? <ExternalLink href={passport.sourceUrl}>{passport.source}</ExternalLink> : passport.source}</dd></div>
        <div className="kv"><dt className="k">{tr({ en: 'Access', fr: 'Accès' })}</dt><dd className="v">{passport.accessMethod}</dd></div>
        <div className="kv"><dt className="k">{tr({ en: 'Licence', fr: 'Licence' })}</dt><dd className="v">{passport.licenceUrl ? <ExternalLink href={passport.licenceUrl}>{licence}</ExternalLink> : licence}</dd></div>
        <div className="kv"><dt className="k">{tr({ en: 'Retrieved', fr: 'Récupéré' })}</dt><dd className="v">{passport.retrievedOn ? fmtDate(passport.retrievedOn, lang) : tr({ en: 'Not retrieved', fr: 'Non récupéré' })}</dd></div>
        <div className="kv"><dt className="k">{tr({ en: 'Coverage', fr: 'Couverture' })}</dt><dd className="v">{passport.coverage ? `${passport.coverage.start} → ${passport.coverage.end}` : '—'} · {passport.frequency}</dd></div>
        <div className="kv"><dt className="k">{tr({ en: 'Rows · version', fr: 'Lignes · version' })}</dt><dd className="v">{passport.rowCount === null ? '—' : fmtNumber(passport.rowCount, lang, 0)} · <span className="mono">{passport.dataVersion ?? '—'}</span></dd></div>
        <div className="kv"><dt className="k">{tr({ en: 'Availability rule', fr: 'Règle de disponibilité' })}</dt><dd className="v">{tr(passport.availabilityRule)}</dd></div>
      </dl>
      <h3 className="h4">{tr({ en: 'Schema', fr: 'Schéma' })}</h3>
      {passport.schema.length === 0 ? <p className="small muted">—</p> : (
        <div className="table-scroll" role="region" aria-label={tr({ en: 'Schema', fr: 'Schéma' })} tabIndex={0}>
          <table className="data-table">
            <thead><tr><th scope="col">{tr({ en: 'Field', fr: 'Champ' })}</th><th scope="col">Type</th><th scope="col">{tr({ en: 'Description', fr: 'Description' })}</th></tr></thead>
            <tbody>{passport.schema.map(f => <tr key={f.name}><th scope="row" className="mono">{f.name}</th><td className="mono">{f.type}</td><td>{f.description}</td></tr>)}</tbody>
          </table>
        </div>
      )}
      <h3 className="h4">{tr({ en: 'Processing', fr: 'Traitement' })}</h3>
      {passport.processing.length === 0 ? <p className="small muted">—</p> : <ol className="bullets">{passport.processing.map((step, i) => <li key={i}>{tr(step)}</li>)}</ol>}
      <h3 className="h4">{tr({ en: 'Quality checks', fr: 'Contrôles de qualité' })}</h3>
      {passport.checks.length === 0
        ? <p className="small muted">{tr({ en: 'No check results recorded.', fr: 'Aucun résultat de contrôle enregistré.' })}</p>
        : (
          <ul className="list-plain small">
            {passport.checks.map((c, i) => (
              <li key={`${c.name}-${i}`}><span aria-hidden="true">{c.ok ? '✓ ' : '✕ '}</span><strong>{c.name}</strong> — {c.ok ? tr({ en: 'passed', fr: 'réussi' }) : tr({ en: 'failed', fr: 'échoué' })} · {c.detail} · {fmtDateTime(c.checkedAt, lang)}</li>
            ))}
          </ul>
        )}
      <LimitationList codes={passport.limitations} />
    </div>
  );
}
