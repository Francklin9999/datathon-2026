'use client';
/**
 * ALFRED macro-vintage rights status for the Time Machine (GET /timemachine/vintages/status).
 * Reports state only: no vintage is fetched or used, so revised macro series stay withheld in
 * replays. Any failure, and fixture mode (no backend), shows the same "unavailable" wording.
 */
import { useEffect, useState } from 'react';
import { API_BASE, FIXTURES_ENABLED } from '../../api/index';
import { useApp } from '../../state/app';

type Vintages = { status: string; missing: string[]; reason: string; terms_url: string };

const TERMS_URL = 'https://fred.stlouisfed.org/legal/';

export function VintageStatus() {
  const { tr, sessionId } = useApp();
  const [status, setStatus] = useState<Vintages | null>(null);
  useEffect(() => {
    if (!sessionId || FIXTURES_ENABLED) return;
    const controller = new AbortController();
    fetch(`${API_BASE}/timemachine/vintages/status`, { signal: controller.signal, headers: { 'X-Aplomb-Session': sessionId } })
      .then(response => (response.ok ? response.json() as Promise<Vintages> : null))
      .then(data => { if (!controller.signal.aborted) setStatus(data); })
      .catch(() => { if (!controller.signal.aborted) setStatus(null); });
    return () => controller.abort();
  }, [sessionId]);
  return <p className="small muted">
    <strong>{tr({ en: 'Macro vintages (ALFRED)', fr: 'Millésimes macro (ALFRED)' })}:</strong>{' '}
    {status?.status === 'rights_confirmed_ingestion_not_wired'
      ? tr({ en: 'operator rights confirmed, but no vintage ingestion exists in this build.', fr: 'droits confirmés par l’opérateur, mais aucune ingestion de millésimes n’existe dans cette version.' })
      : tr({ en: 'unavailable.', fr: 'indisponible.' })}{' '}
    {tr({ en: 'FRED/ALFRED terms restrict use with AI systems, caching and redistribution, so no vintage is fetched or used; revised macro series stay withheld in replays.', fr: 'Les conditions FRED/ALFRED limitent l’usage avec des systèmes d’IA, la mise en cache et la redistribution : aucun millésime n’est récupéré ni utilisé; les séries macro révisées restent retenues dans les rejeux.' })}{' '}
    <a href={status?.terms_url ?? TERMS_URL} target="_blank" rel="noreferrer">{tr({ en: 'Terms', fr: 'Conditions' })}</a>
  </p>;
}
