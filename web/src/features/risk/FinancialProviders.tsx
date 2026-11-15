'use client';
import { useState } from 'react';
import { getApiClient } from '../../api/index';
import { asApiError, type ApiRequestError } from '../../api/errors';
import { useApp } from '../../state/app';
import { useQuery } from '../../state/useQuery';
import { Card } from '../../components/common/Page';
import { ErrorState, Loading } from '../../components/common/States';
import { ExternalLink } from '../../components/common/ExternalLink';

export function FinancialProviders() {
  const { sessionId, tr } = useApp();
  const providers = useQuery(sessionId ? `financial-providers|${sessionId}` : null, signal => getApiClient().financialProviders(signal));
  const [id, setId] = useState('');
  const [day, setDay] = useState('');
  const [symbol, setSymbol] = useState('SPY');
  const [sheet, setSheet] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiRequestError | null>(null);
  const [result, setResult] = useState<Awaited<ReturnType<ReturnType<typeof getApiClient>['captureFinancialProvider']>> | null>(null);
  const selected = providers.data?.providers.find(p => p.id === id);
  const reset = () => { setResult(null); setError(null); };
  const capture = async () => {
    setBusy(true); reset();
    try { setResult(await getApiClient().captureFinancialProvider(id, { asOf: day, symbol, sheet, limit: 100 })); }
    catch (e) { setError(asApiError(e)); } finally { setBusy(false); }
  };
  return <Card title={tr({ en: 'Additional public financial feeds', fr: 'Autres sources financières publiques' })}>
    <p>{tr({ en: 'Free anonymous-access sources only. Paid feeds are excluded; account, login and API-key sources are set aside. Public download access and permission to reuse data are separate. A feed awaiting data-use permission cannot be fetched.', fr: 'Sources gratuites accessibles sans connexion. Les sources payantes sont exclues; celles avec compte, connexion ou clé API sont mises de côté. L’accès public et le droit de réutilisation sont distincts. Sans permission d’utilisation, aucune acquisition n’est effectuée.' })}</p>
    {providers.loading && <Loading />}{providers.error && <ErrorState error={providers.error} onRetry={providers.reload} />}
    {providers.data && <><div className="table-scroll" role="region" tabIndex={0} aria-label={tr({ en: 'Public provider availability', fr: 'Disponibilité des fournisseurs publics' })}><table><thead><tr><th>{tr({ en: 'Source', fr: 'Source' })}</th><th>{tr({ en: 'Availability', fr: 'Disponibilité' })}</th><th>{tr({ en: 'Scope', fr: 'Portée' })}</th></tr></thead><tbody>{providers.data.providers.map(p => <tr key={p.id}><th scope="row"><ExternalLink href={p.documentation}>{p.name}</ExternalLink></th><td>{p.status === 'permission_required' ? tr({ en: 'Awaiting data-use permission', fr: 'Permission d’utilisation requise' }) : p.status.replaceAll('_', ' ')}</td><td>{p.limitation}</td></tr>)}</tbody></table></div>
      <details><summary>{tr({ en: 'Set-aside sources', fr: 'Sources mises de côté' })}</summary><ul>{providers.data.setAside.map(p => <li key={p.id}>{p.name}: {p.reason}</li>)}</ul></details>
      <form onSubmit={e => { e.preventDefault(); void capture(); }}><fieldset disabled={busy}><div className="form-grid">
        <div className="field"><label htmlFor="financial-provider">{tr({ en: 'Public source', fr: 'Source publique' })}</label><select id="financial-provider" required value={id} onChange={e => { setId(e.target.value); reset(); }}><option value="">—</option>{providers.data.providers.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></div>
        <div className="field"><label htmlFor="financial-provider-day">{tr({ en: 'Observation cutoff / daily report date', fr: 'Date limite / date du rapport quotidien' })}</label><input id="financial-provider-day" type="date" required value={day} onChange={e => { setDay(e.target.value); reset(); }} /></div>
        {id === 'finra-volume' && <div className="field"><label htmlFor="financial-provider-symbol">{tr({ en: 'Exact reported symbol', fr: 'Symbole exact du rapport' })}</label><input id="financial-provider-symbol" required maxLength={30} pattern="[A-Z0-9.\-]+" value={symbol} onChange={e => { setSymbol(e.target.value.toUpperCase()); reset(); }} /></div>}
        {id === 'aqr' && <div className="field"><label htmlFor="financial-provider-sheet">{tr({ en: 'Workbook data sheet (optional)', fr: 'Feuille de données (facultative)' })}</label><input id="financial-provider-sheet" maxLength={80} value={sheet} onChange={e => { setSheet(e.target.value); reset(); }} /></div>}
      </div>{selected && <p className="small muted">{selected.limitation}{id === 'aqr' ? tr({ en: ' Use today’s date: workbook inspection is current-capture only.', fr: ' Utilisez la date du jour : inspection de la capture actuelle seulement.' }) : ''} · <ExternalLink href={selected.terms}>{tr({ en: 'Provider terms', fr: 'Conditions du fournisseur' })}</ExternalLink></p>}
      <button type="submit" className="btn" disabled={!selected || selected.status !== 'configured'}>{tr({ en: 'Fetch permitted public data', fr: 'Charger les données publiques autorisées' })}</button></fieldset></form>
    </>}
    {error && <ErrorState error={error} />}
    {result && <div role="status"><p><strong>{result.label}</strong> · {result.unit} · {result.records.length} {tr({ en: 'source records', fr: 'observations sources' })}</p><p className="small">{tr({ en: 'Observation cutoff', fr: 'Date limite' })}: {result.asOf} · {tr({ en: 'Known since capture', fr: 'Connu depuis la capture' })}: {result.availableAt}</p><ExternalLink href={result.source.sourceUrl}>{tr({ en: 'Original provider', fr: 'Fournisseur original' })}</ExternalLink><p className="small mono" style={{ overflowWrap: 'anywhere' }}>{result.source.rawSha256} · {result.version}</p>
      <div className="table-scroll" role="region" tabIndex={0} aria-label={tr({ en: 'Captured source records', fr: 'Observations capturées' })}><table><thead><tr><th>#</th><th>{tr({ en: 'Reported fields', fr: 'Champs publiés' })}</th></tr></thead><tbody>{result.records.map((row, i) => <tr key={i}><td>{i + 1}</td><td><pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify(row, null, 2)}</pre></td></tr>)}</tbody></table></div>{result.limitations.map(l => <p className="small muted" key={l}>{l}</p>)}
    </div>}
  </Card>;
}
