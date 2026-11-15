'use client';
import { useState, type ReactNode } from 'react';
import type { FactorFitResult, FundLookThroughResult } from '../../api/investorModels';
import { parseModelInput } from '../../api/investorModels';
import { getApiClient } from '../../api/index';
import { asApiError, type ApiRequestError } from '../../api/errors';
import { Card } from '../../components/common/Page';
import { ErrorState } from '../../components/common/States';
import { ExternalLink } from '../../components/common/ExternalLink';
import { useApp } from '../../state/app';
import { fmtNumber, fmtPct, fmtSignedPct } from '../../lib/format';

/** A bounded data-only import. The backend validates the complete model-specific structure. */
function ModelImport<T>({ id, request, children }: {
  id: string;
  request: (input: Record<string, unknown>) => Promise<T>;
  children: (result: T) => ReactNode;
}) {
  const { tr } = useApp();
  const [input, setInput] = useState('');
  const [result, setResult] = useState<T | null>(null);
  const [invalid, setInvalid] = useState(false);
  const [error, setError] = useState<ApiRequestError | null>(null);
  const [busy, setBusy] = useState(false);
  const reset = () => { setResult(null); setInvalid(false); setError(null); };
  const calculate = async () => {
    reset();
    let data: Record<string, unknown>;
    try { data = parseModelInput(input); }
    catch { setInvalid(true); return; }
    setBusy(true);
    try { setResult(await request(data)); }
    catch (e) { setError(asApiError(e)); }
    finally { setBusy(false); }
  };
  const upload = async (file: File | undefined) => {
    reset();
    if (!file) return;
    if (file.size > 240_000) { setInvalid(true); return; }
    try { setInput(await file.text()); }
    catch { setInvalid(true); }
  };
  return <>
    <form onSubmit={e => { e.preventDefault(); void calculate(); }}>
      <fieldset disabled={busy}>
        <div className="field"><label htmlFor={`${id}-file`}>{tr({ en: 'Import JSON file', fr: 'Importer un fichier JSON' })}</label>
          <input id={`${id}-file`} type="file" accept="application/json,.json" onChange={e => { void upload(e.target.files?.[0]); e.target.value = ''; }} /></div>
        <div className="field"><label htmlFor={`${id}-json`}>{tr({ en: 'Or paste JSON data', fr: 'Ou coller des données JSON' })}</label>
          <textarea id={`${id}-json`} rows={8} value={input} onChange={e => { setInput(e.target.value); reset(); }} spellCheck={false} />
          <span className="hint">{tr({ en: 'Maximum 240 kB. Only JSON data is accepted.', fr: 'Maximum 240 ko. Seules les données JSON sont acceptées.' })}</span></div>
        <button type="submit" className="btn" disabled={!input.trim()}>{busy ? tr({ en: 'Calculating…', fr: 'Calcul…' }) : tr({ en: 'Calculate', fr: 'Calculer' })}</button>
      </fieldset>
    </form>
    {invalid && <p role="alert" className="field-error">{tr({ en: 'Enter a valid JSON object of at most 240 kB.', fr: 'Saisissez un objet JSON valide de 240 ko au maximum.' })}</p>}
    {error && <ErrorState error={error} />}
    {result !== null && <div role="status">{children(result)}</div>}
  </>;
}

function FactorResults({ result }: { result: FactorFitResult }) {
  const { tr, lang } = useApp();
  return <>
    <p><strong>{tr({ en: 'Descriptive fitted exposure', fr: 'Exposition descriptive estimée' })}</strong> · {result.firstStart} — {result.lastEnd} · {result.observations} {tr({ en: 'aligned periods', fr: 'périodes alignées' })}</p>
    <dl className="kv-list"><div className="kv"><dt className="k">{tr({ en: 'Intercept per period', fr: 'Ordonnée à l’origine par période' })}</dt><dd className="v">{fmtSignedPct(result.alphaPerPeriod * 100, lang, 3)}</dd></div>
      <div className="kv"><dt className="k">{tr({ en: 'Residual standard deviation per period', fr: 'Écart-type résiduel par période' })}</dt><dd className="v">{result.residualStdev === null ? '—' : fmtPct(result.residualStdev * 100, lang, 3)}</dd></div>
      <div className="kv"><dt className="k">R²</dt><dd className="v">{result.rSquared === null ? tr({ en: 'Undefined', fr: 'Indéfini' }) : fmtNumber(result.rSquared, lang, 3)}</dd></div>
      {Object.entries(result.betas).map(([name, beta]) => <div className="kv" key={name}><dt className="k">{name} · β</dt><dd className="v">{fmtNumber(beta, lang, 3)}</dd></div>)}
    </dl>
    <p className="small muted">{tr({ en: 'Excluded unmatched return periods', fr: 'Périodes de rendement sans correspondance' })}: {result.excludedReturns} · {tr({ en: 'Excluded unmatched factor periods', fr: 'Périodes de facteurs sans correspondance' })}: {result.excludedFactors}</p>
    <p className="small">{tr({ en: 'Caller-provided source references', fr: 'Références fournies' })}: {result.sourceIds.join(', ') || '—'}</p>
    {result.limitations.map((note, i) => <p className="small muted" key={i}>{note}</p>)}
  </>;
}

function FundResults({ result }: { result: FundLookThroughResult }) {
  const { tr, lang } = useApp();
  return <>
    <p><strong>{tr({ en: 'Unresolved portfolio weight', fr: 'Poids du portefeuille non résolu' })}: {fmtPct(result.unresolvedWeight * 100, lang, 3)}</strong></p>
    {([['direct', tr({ en: 'Direct holdings', fr: 'Positions directes' }), result.direct], ['indirect', tr({ en: 'Disclosed indirect holdings', fr: 'Positions indirectes divulguées' }), result.indirect]] as const).map(([key, label, holdings]) => <div key={key}>
      <h3>{label}</h3>{Object.keys(holdings).length === 0 ? <p>—</p> : <div className="table-scroll" role="region" aria-label={label} tabIndex={0}><table><thead><tr><th>ISIN</th><th>{tr({ en: 'Portfolio weight', fr: 'Poids du portefeuille' })}</th></tr></thead><tbody>
        {Object.entries(holdings).map(([isin, weight]) => <tr key={isin}><th scope="row">{isin}</th><td>{fmtPct(weight * 100, lang, 3)}</td></tr>)}
      </tbody></table></div>}
    </div>)}
    <h3>{tr({ en: 'Disclosed overlap lower bounds', fr: 'Bornes inférieures de chevauchement divulgué' })}</h3>
    {result.overlap.length === 0 ? <p>{tr({ en: 'No pair of supplied fund snapshots to compare.', fr: 'Aucune paire de fonds fournie à comparer.' })}</p> : <ul>{result.overlap.map((pair, i) => <li key={i}>{pair.firstIsin} / {pair.secondIsin}: {fmtPct(pair.weight * 100, lang, 3)}</li>)}</ul>}
    <details><summary>{tr({ en: 'Inspect supplied snapshot evidence', fr: 'Examiner les preuves fournies' })}</summary>
      {Object.entries(result.sources).map(([isin, source]) => <div key={isin}>
        <h4>{isin} · {result.snapshotDates[isin]} · {source.source_id}</h4>
        <p><ExternalLink href={source.url}>{source.url}</ExternalLink></p>
        <p className="small muted">{tr({ en: 'Available', fr: 'Disponible' })}: {source.available_at} · {tr({ en: 'Retrieved', fr: 'Récupéré' })}: {source.retrieved_at} · {source.licence}</p>
        <p className="small mono" style={{ overflowWrap: 'anywhere' }}>SHA-256: {source.content_sha256}</p>
        {source.limitations.map((note, i) => <p className="small muted" key={i}>{note}</p>)}
      </div>)}
    </details>
    {result.limitations.map((note, i) => <p className="small muted" key={i}>{note}</p>)}
  </>;
}

/** Data inputs are intentionally independent of the active profile until verified feeds are integrated. */
export function ModelInputs() {
  const { tr } = useApp();
  return <>
    <Card title={tr({ en: 'Factor exposure from supplied samples', fr: 'Exposition factorielle à partir d’échantillons fournis' })}>
      <p>{tr({ en: 'Provide your own dated portfolio returns and factor observations. These inputs are not derived from the active profile and their source and currency are not verified. Returns and risk-free values must be decimal fractions, in the same currency and over identical start/end periods. At least 30 aligned, non-overlapping periods are required. The fit is descriptive, not a forecast.', fr: 'Fournissez vos propres rendements de portefeuille et observations factorielles datés. Ils ne proviennent pas automatiquement du profil actif et leur source et devise ne sont pas vérifiées. Rendements et taux sans risque sont des fractions décimales, dans une même devise et sur des dates de début et de fin identiques. Il faut au moins 30 périodes alignées sans chevauchement. Le calcul décrit l’échantillon sans prévoir l’avenir.' })}</p>
      <details><summary>{tr({ en: 'Required JSON fields', fr: 'Champs JSON requis' })}</summary><p className="small">{tr({ en: 'An object with names (array of factor names), returns (array of {start, end, value}), and factors (array of {start, end, riskFree, factors, source}). Each factors field is an object mapping every named factor to its decimal return. Dates use YYYY-MM-DD; source is a source reference or explicit hypothetical assumption.', fr: 'Un objet avec names (liste de noms de facteurs), returns (liste de {start, end, value}) et factors (liste de {start, end, riskFree, factors, source}). Chaque champ factors associe les noms des facteurs à leurs rendements décimaux. Dates au format AAAA-MM-JJ; source indique une référence ou hypothèse explicite.' })}</p></details>
      <ModelImport id="factor-fit" request={body => getApiClient().factorFit(body)}>{result => <FactorResults result={result} />}</ModelImport>
    </Card>
    <Card title={tr({ en: 'Fund look-through from supplied disclosures', fr: 'Décomposition de fonds à partir de déclarations fournies' })}>
      <p>{tr({ en: 'Supply exact ISIN positions and dated constituent snapshots. Inputs, rights and provenance are caller-supplied and unverified; they are not linked automatically to the active portfolio. Partial disclosures leave an unresolved remainder. The same ISIN check does not prove issuer identity. Historical mode also requires the capture to have been retrieved by the cutoff.', fr: 'Fournissez les positions par ISIN exact et les compositions datées. Données, droits et provenance sont fournis sans vérification et ne sont pas reliés automatiquement au portefeuille actif. Une divulgation partielle laisse un solde non résolu. Le contrôle ISIN ne prouve pas l’identité de l’émetteur. En mode historique, la capture doit aussi avoir été récupérée avant la date limite.' })}</p>
      <details><summary>{tr({ en: 'Required JSON fields', fr: 'Champs JSON requis' })}</summary><p className="small">{tr({ en: 'An object with asOf (YYYY-MM-DD), historical (boolean), positions (ISIN → portfolio fraction) and snapshots (array). Each snapshot has fundIsin, holdingsDate, constituents (array of {isin, weight} as fund fractions), and evidence. Evidence requires source_id, HTTPS url, content_sha256, available_at, retrieved_at and licence; timestamps include timezone. Optional evidence fields are observed_at, published_at and limitations. Weights are fractions, not percentages.', fr: 'Un objet avec asOf (AAAA-MM-JJ), historical (booléen), positions (ISIN → fraction du portefeuille) et snapshots (liste). Chaque fonds indique fundIsin, holdingsDate, constituents (liste de {isin, weight}, fractions du fonds) et evidence. La preuve exige source_id, url HTTPS, content_sha256, available_at, retrieved_at et licence; heures avec fuseau. observed_at, published_at et limitations sont facultatifs. Les poids sont des fractions, non des pourcentages.' })}</p></details>
      <ModelImport id="fund-look-through" request={body => getApiClient().fundLookThrough(body)}>{result => <FundResults result={result} />}</ModelImport>
    </Card>
  </>;
}
